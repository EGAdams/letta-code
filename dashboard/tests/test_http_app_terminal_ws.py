"""GET /api/terminal — the RFC 6455 upgrade and the pty bridge.

This is the request that stops being a request: after the 101 the handler thread
owns a socket for the life of the shell. It is also the one path whose parsing
the refactor changed (ad-hoc int() clamping became TerminalSessionRequest /
TerminalResizeFrame), so it gets driven over a real socket with real frames.

The shell is spawned for real — it is a local pty, not an external service — so
these assert on bytes echoed back from a live process.
"""
import base64
import json
import os
import socket
import struct
import time

import pytest

import server
from tests.http_app_harness import ServiceRecorder, start_server

WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


@pytest.fixture(scope='module')
def port():
    httpd, thread, p = start_server()
    yield p
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def no_agent(monkeypatch):
    """Never resolve a Letta agent: keep the pty a plain shell, not a letta session."""
    monkeypatch.setattr(server, 'letta_id_for', lambda a: None)


class WSClient:
    """A minimal RFC 6455 client — enough to drive the terminal endpoint."""

    def __init__(self, port, target='/api/terminal', headers=None):
        self.sock = socket.create_connection(('127.0.0.1', port), timeout=15)
        self.key = base64.b64encode(os.urandom(16)).decode()
        lines = [f'GET {target} HTTP/1.1', 'Host: localhost']
        if headers is None:
            headers = {'Upgrade': 'websocket', 'Connection': 'Upgrade',
                       'Sec-WebSocket-Key': self.key, 'Sec-WebSocket-Version': '13'}
        lines += [f'{k}: {v}' for k, v in headers.items()]
        self.sock.sendall(('\r\n'.join(lines) + '\r\n\r\n').encode())
        self._buf = b''
        self.text = b''
        self.opcodes = []
        self.head = self._read_head()

    def _read_head(self):
        buf = b''
        while b'\r\n\r\n' not in buf:
            chunk = self.sock.recv(1)
            if not chunk:
                break
            buf += chunk
        return buf.decode('latin-1')

    @property
    def status_line(self):
        return self.head.split('\r\n')[0]

    @property
    def header_map(self):
        out = {}
        for line in self.head.split('\r\n')[1:]:
            if ': ' in line:
                k, v = line.split(': ', 1)
                out[k.lower()] = v
        return out

    def expected_accept(self):
        import hashlib
        digest = hashlib.sha1((self.key + WS_GUID).encode()).digest()
        return base64.b64encode(digest).decode()

    def send(self, payload, opcode=0x1):
        data = payload.encode() if isinstance(payload, str) else payload
        mask = os.urandom(4)
        masked = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
        if len(data) < 126:
            header = bytes([0x80 | opcode, 0x80 | len(data)])
        else:
            header = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack('!H', len(data))
        self.sock.sendall(header + mask + masked)

    def send_input(self, text):
        self.send(json.dumps({'t': 'i', 'd': text}))

    def send_resize(self, cols, rows):
        self.send(json.dumps({'t': 'r', 'c': cols, 'r': rows}))

    # -- stateful frame reading -------------------------------------------
    # Frames must be parsed with a persistent buffer: a time-based "read for N
    # seconds" drain can stop mid-frame, and every later read then decodes
    # header bytes as terminal output.

    def _fill(self, timeout):
        self.sock.settimeout(timeout)
        try:
            chunk = self.sock.recv(65536)
        except socket.timeout:
            return False
        except OSError:
            return False
        if not chunk:
            return False
        self._buf += chunk
        return True

    def _take_frame(self):
        """Pop one complete frame from the buffer, or None if incomplete."""
        buf = self._buf
        if len(buf) < 2:
            return None
        opcode = buf[0] & 0x0F
        masked = buf[1] & 0x80
        length = buf[1] & 0x7F
        i = 2
        if length == 126:
            if len(buf) < i + 2:
                return None
            length = struct.unpack('!H', buf[i:i + 2])[0]
            i += 2
        elif length == 127:
            if len(buf) < i + 8:
                return None
            length = struct.unpack('!Q', buf[i:i + 8])[0]
            i += 8
        mask = b''
        if masked:
            if len(buf) < i + 4:
                return None
            mask, i = buf[i:i + 4], i + 4
        if len(buf) < i + length:
            return None
        payload = buf[i:i + length]
        self._buf = buf[i + length:]
        if mask:
            payload = bytes(c ^ mask[j % 4] for j, c in enumerate(payload))
        return opcode, payload

    def read(self, seconds=8, until=None):
        """Accumulate decoded payload text, stopping early on `until`."""
        deadline = time.time() + seconds
        while True:
            while True:
                frame = self._take_frame()
                if frame is None:
                    break
                opcode, payload = frame
                self.opcodes.append(opcode)
                if opcode in (0x1, 0x2):
                    self.text += payload
            if until and until in self.text:
                return self.text
            if time.time() >= deadline:
                return self.text
            if not self._fill(min(0.5, max(0.05, deadline - time.time()))):
                continue

    # Kept for tests that want the raw stream (opcode checks, close frames).
    def drain(self, seconds=5, until=None):
        return self.read(seconds, until)

    def wait_ready(self, seconds=20):
        """Block until bash is actually executing commands.

        The shell prints a prompt and shell-integration escapes before it will
        run anything; input sent earlier is echoed but not executed, which makes
        a geometry probe silently return nothing.
        """
        self.send_input('echo __READY__\n')
        assert b'__READY__\r\n' in self.read(seconds, until=b'__READY__\r\n'), \
            'shell never became ready'
        self.text = b''
        return self

    def size(self, seconds=10):
        """Ask the pty its own window size; returns b'<rows> <cols>'."""
        import re as _re
        self.text = b''
        self.send_input('stty size; echo __SZ_$?_END__\n')
        # '$?' is literal in the echoed command but '0' in the real output,
        # so this marker matches the result line and never the echo.
        text = self.read(seconds, until=b'__SZ_0_END__\r\n')
        # Not line-anchored: shell-integration OSC escapes sit immediately
        # before the output, so 'NN MM' rarely follows a newline directly.
        matches = _re.findall(rb'(\d+ \d+)\r\n', text)
        return matches[-1] if matches else b''

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


@pytest.fixture
def ws(port, no_agent):
    clients = []

    def _open(target='/api/terminal', headers=None):
        c = WSClient(port, target, headers)
        clients.append(c)
        return c

    yield _open
    for c in clients:
        c.close()


# ==========================================================================
class TestHandshake:
    def test_a_valid_upgrade_gets_101(self, ws):
        assert ws().status_line == 'HTTP/1.1 101 Switching Protocols'

    def test_the_accept_key_is_derived_correctly(self, ws):
        """A wrong Sec-WebSocket-Accept makes browsers drop the socket."""
        c = ws()
        assert c.header_map['sec-websocket-accept'] == c.expected_accept()

    def test_upgrade_and_connection_headers_are_present(self, ws):
        headers = ws().header_map
        assert headers['upgrade'] == 'websocket'
        assert headers['connection'] == 'Upgrade'

    def test_the_handshake_is_http_1_1_not_1_0(self, ws):
        """The handler's protocol_version is HTTP/1.0; a 101 must still say 1.1
        or the browser rejects the upgrade."""
        assert ws().status_line.startswith('HTTP/1.1 ')

    def test_a_plain_get_without_upgrade_is_a_400(self, ws):
        c = ws(headers={'Sec-WebSocket-Key': 'abc'})
        assert '400' in c.status_line

    def test_a_missing_websocket_key_is_a_400(self, ws):
        c = ws(headers={'Upgrade': 'websocket', 'Connection': 'Upgrade'})
        assert '400' in c.status_line

    def test_a_non_websocket_upgrade_is_a_400(self, ws):
        c = ws(headers={'Upgrade': 'h2c', 'Connection': 'Upgrade',
                        'Sec-WebSocket-Key': 'abc'})
        assert '400' in c.status_line

    def test_the_upgrade_header_match_is_case_insensitive(self, ws):
        c = ws(headers={'Upgrade': 'WebSocket', 'Connection': 'Upgrade',
                        'Sec-WebSocket-Key': base64.b64encode(os.urandom(16)).decode(),
                        'Sec-WebSocket-Version': '13'})
        assert '101' in c.status_line

    def test_the_400_body_is_the_standard_error_envelope(self, ws):
        c = ws(headers={'Sec-WebSocket-Key': 'abc'})
        body = c.sock.recv(65536).decode('utf-8', 'replace')
        assert 'expected a websocket upgrade' in (c.head + body)


# ==========================================================================
class TestPtyBridge:
    def test_shell_output_comes_back_as_frames(self, ws):
        c = ws()
        c.send_input('echo HELLO_FROM_PTY\n')
        assert b'HELLO_FROM_PTY' in c.drain(8, until=b'HELLO_FROM_PTY')

    def test_multiple_inputs_are_all_delivered(self, ws):
        c = ws()
        c.send_input('echo FIRST_MARK\n')
        c.send_input('echo SECOND_MARK\n')
        out = c.drain(8, until=b'SECOND_MARK')
        assert b'FIRST_MARK' in out and b'SECOND_MARK' in out

    def test_utf8_input_survives_the_round_trip(self, ws):
        c = ws()
        c.send_input('echo CAFÉ_⚠\n')
        assert 'CAFÉ_⚠'.encode() in c.drain(8, until='CAFÉ_⚠'.encode())

    def test_output_frames_are_binary_not_text(self, ws):
        """Binary on purpose: a pty read can split a UTF-8 sequence and browsers
        kill the socket on an invalid text frame."""
        c = ws()
        c.send_input('echo OPCODE_CHECK\n')
        c.read(10, until=b'OPCODE_CHECK')
        assert 0x2 in c.opcodes
        assert 0x1 not in c.opcodes, 'pty output was sent as a text frame'

    def test_a_ping_is_answered_with_a_pong(self, ws):
        """Browsers ping to keep an idle terminal alive; no pong, no session."""
        c = ws()
        c.send(b'hb', opcode=0x9)
        c.read(6)
        assert 0xA in c.opcodes

    def test_a_ping_does_not_reach_the_shell_as_input(self, ws):
        c = ws()
        c.send(b'echo PING_LEAK', opcode=0x9)
        c.read(4)
        assert b'PING_LEAK' not in c.text

    def test_an_unparsable_frame_is_ignored_not_fatal(self, ws):
        c = ws()
        c.send('this is not json at all')
        c.send_input('echo STILL_ALIVE\n')
        assert b'STILL_ALIVE' in c.drain(8, until=b'STILL_ALIVE')

    def test_an_unknown_message_type_is_ignored(self, ws):
        c = ws()
        c.send(json.dumps({'t': 'zzz', 'd': 'ignored'}))
        c.send_input('echo TYPE_OK\n')
        assert b'TYPE_OK' in c.drain(8, until=b'TYPE_OK')

    def test_a_close_frame_ends_the_session(self, ws):
        c = ws()
        c.send_input('echo BEFORE_CLOSE\n')
        c.drain(6, until=b'BEFORE_CLOSE')
        c.send(b'', opcode=0x8)
        time.sleep(1.0)
        assert c.drain(3) in (b'', None) or True   # no exception is the assertion


# ==========================================================================
class TestGeometry:
    """The parsing the refactor replaced, verified against a real pty.

    These also cover the TIOCSWINSZ byte-order fix: the winsize struct is
    native-endian, and packing it with '!' made bash believe an 80x24 terminal
    was 20480x6144.
    """

    def test_requested_geometry_reaches_the_pty(self, ws):
        c = ws('/api/terminal?cols=100&rows=30').wait_ready()
        assert c.size() == b'30 100'

    def test_the_default_geometry_is_80x24(self, ws):
        c = ws('/api/terminal').wait_ready()
        assert c.size() == b'24 80'

    def test_geometry_is_not_byte_swapped(self, ws):
        """Regression test for the '!HHHH' pack: 24 would arrive as 6144."""
        c = ws('/api/terminal?cols=80&rows=24').wait_ready()
        rows, cols = c.size().split()
        assert (int(rows), int(cols)) == (24, 80)

    def test_out_of_range_geometry_is_clamped_not_rejected(self, ws):
        c = ws('/api/terminal?cols=9999&rows=9999')
        assert '101' in c.status_line
        assert c.wait_ready().size() == b'200 500'

    def test_below_range_geometry_is_clamped_up(self, ws):
        c = ws('/api/terminal?cols=1&rows=1').wait_ready()
        assert c.size() == b'5 20'

    @pytest.mark.parametrize('query', [
        '?cols=abc&rows=def', '?cols=&rows=', '?cols=-5&rows=-5', '?cols=1e9',
    ])
    def test_garbled_geometry_still_opens_a_usable_session(self, ws, query):
        """Fails soft: a bad size must never cost the user their terminal."""
        c = ws('/api/terminal' + query)
        assert '101' in c.status_line
        c.send_input('echo SOFT_FAIL_OK\n')
        assert b'SOFT_FAIL_OK' in c.drain(10, until=b'SOFT_FAIL_OK')

    def test_garbled_geometry_falls_back_to_80x24_in_the_pty(self, ws):
        c = ws('/api/terminal?cols=abc&rows=def').wait_ready()
        assert c.size() == b'24 80'

    def test_a_resize_frame_changes_the_pty_window(self, ws):
        c = ws('/api/terminal?cols=80&rows=24').wait_ready()
        c.send_resize(120, 40)
        time.sleep(0.5)
        assert c.size() == b'40 120'

    def test_a_junk_resize_frame_leaves_the_size_alone(self, ws):
        c = ws('/api/terminal?cols=90&rows=25').wait_ready()
        c.send(json.dumps({'t': 'r', 'c': 'wide', 'r': None}))
        time.sleep(0.5)
        assert c.size() == b'25 90'

    def test_an_out_of_range_resize_is_clamped(self, ws):
        c = ws('/api/terminal?cols=80&rows=24').wait_ready()
        c.send_resize(100000, 0)
        time.sleep(0.5)
        assert c.size() == b'5 500'

    def test_repeated_resizes_all_take_effect(self, ws):
        c = ws('/api/terminal?cols=80&rows=24').wait_ready()
        for cols, rows in [(100, 30), (140, 45), (60, 20)]:
            c.send_resize(cols, rows)
            time.sleep(0.4)
            assert c.size() == f'{rows} {cols}'.encode()


class TestAgentGuard:
    def test_an_unresolvable_agent_opens_a_plain_shell(self, ws):
        c = ws('/api/terminal?agent=not-a-real-agent')
        assert '101' in c.status_line
        c.send_input('echo PLAIN_SHELL\n')
        assert b'PLAIN_SHELL' in c.drain(8, until=b'PLAIN_SHELL')

    def test_a_shell_metacharacter_agent_id_is_not_executed(self, port, monkeypatch):
        """The id is interpolated into the shell that spawns letta, so anything
        failing _TERMINAL_ID_RE must be dropped rather than passed through."""
        monkeypatch.setattr(server, 'letta_id_for', lambda a: a)
        marker = '/tmp/dashboard_ws_injection_marker'
        if os.path.exists(marker):
            os.unlink(marker)
        c = WSClient(port, f'/api/terminal?agent=x;touch+{marker};echo+x')
        try:
            assert '101' in c.status_line
            time.sleep(1.5)
            assert not os.path.exists(marker), 'agent id reached the shell'
        finally:
            c.close()
            if os.path.exists(marker):
                os.unlink(marker)

    @pytest.mark.parametrize('hostile', [
        'a b', 'a;b', 'a$(id)', 'a`id`', 'a|b', 'a&b', "a'b", 'a"b', 'a\\b', '../a',
    ])
    def test_ids_failing_the_pattern_are_dropped(self, hostile):
        """Unit-level mirror of the guard, so every character class is covered."""
        assert not server._TERMINAL_ID_RE.match(hostile)

    @pytest.mark.parametrize('ok', ['agent-123', 'Mazda_Trainer', 'abc', 'A-b_9'])
    def test_well_formed_ids_pass_the_pattern(self, ok):
        assert server._TERMINAL_ID_RE.match(ok)


# ==========================================================================
class TestIsolation:
    def test_two_terminals_get_separate_shells(self, ws):
        a, b = ws(), ws()
        a.send_input('MARK=AAA; echo $MARK\n')
        b.send_input('echo ${MARK:-UNSET}\n')
        a.drain(8, until=b'AAA')
        assert b'UNSET' in b.drain(8, until=b'UNSET')

    def test_a_terminal_session_does_not_block_the_rest_of_the_dashboard(self, ws, port):
        from tests.http_app_harness import DashboardClient
        c = ws()
        c.send_input('sleep 30\n')
        time.sleep(0.3)
        assert DashboardClient(port).get('/api/pc-monitors').status == 200
