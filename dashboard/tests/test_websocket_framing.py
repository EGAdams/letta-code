"""The hand-rolled RFC 6455 framing.

This is the code with the worst failure signature in the dashboard. A browser
does not report a protocol violation -- it closes the socket. The symptom is a
terminal panel that goes blank, with nothing in any log on either side, and no
way to tell a framing bug from a dead shell.

It is also entirely pure, so it can be pinned against byte literals from the
specification rather than against a live socket. That is what this file does:
every length encoding, masking in both directions, fragmentation, and the
guards that stop a malicious client from allocating memory on this box.
"""
import io
import struct

import pytest

import server
from http_app import websocket as ws


def masked(payload, opcode=0x1, fin=True, mask=b'\x37\xfa\x21\x3d'):
    """Build a client→server frame the way a browser does: always masked."""
    head = bytes([(0x80 if fin else 0) | opcode])
    n = len(payload)
    if n < 126:
        head += bytes([0x80 | n])
    elif n < 65536:
        head += bytes([0x80 | 126]) + struct.pack('!H', n)
    else:
        head += bytes([0x80 | 127]) + struct.pack('!Q', n)
    body = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return head + mask + body


class TestTheHandshake:
    def test_it_matches_the_worked_example_in_rfc_6455(self):
        """§1.3's example, so the constant and the digest are both pinned."""
        assert ws.ws_accept_key('dGhlIHNhbXBsZSBub25jZQ==') == \
            's3pPLMBiTxaQ9kYGzzhZRbK+xOo='

    def test_the_magic_guid_is_the_one_from_the_spec(self):
        assert ws._WS_GUID == '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

    def test_a_different_key_yields_a_different_accept(self):
        a = ws.ws_accept_key('dGhlIHNhbXBsZSBub25jZQ==')
        b = ws.ws_accept_key('x3JJHMbDL1EzLkh9GBhXDw==')
        assert a != b


class TestEncodingServerFrames:
    def test_a_server_frame_is_never_masked(self):
        """The mask bit on a server frame is a protocol violation, and the
        browser's response to one is to close without saying why."""
        out = ws.ws_encode_frame(b'hello')
        assert not out[1] & 0x80

    def test_fin_is_always_set_because_the_server_never_fragments(self):
        assert ws.ws_encode_frame(b'hello')[0] & 0x80

    def test_the_default_opcode_is_binary(self):
        """pty output is raw bytes: a read can split a UTF-8 sequence
        mid-character, and a text frame carrying invalid UTF-8 kills the
        socket. Binary is not a preference here."""
        assert ws.ws_encode_frame(b'\xff\xfe')[0] & 0x0F == 0x2

    @pytest.mark.parametrize('opcode', [0x1, 0x2, 0x8, 0x9, 0xA])
    def test_the_opcode_is_carried_through(self, opcode):
        assert ws.ws_encode_frame(b'', opcode=opcode)[0] & 0x0F == opcode

    def test_a_short_payload_uses_the_single_length_byte(self):
        assert ws.ws_encode_frame(b'x' * 125) == b'\x82\x7d' + b'x' * 125

    def test_the_boundary_at_126_switches_to_the_two_byte_length(self):
        """125 is the last inline length; 126 is the escape value itself."""
        out = ws.ws_encode_frame(b'x' * 126)
        assert out[1] == 126
        assert struct.unpack('!H', out[2:4])[0] == 126

    def test_the_boundary_at_65536_switches_to_the_eight_byte_length(self):
        out = ws.ws_encode_frame(b'x' * 65536)
        assert out[1] == 127
        assert struct.unpack('!Q', out[2:10])[0] == 65536

    def test_65535_is_still_the_two_byte_form(self):
        out = ws.ws_encode_frame(b'x' * 65535)
        assert out[1] == 126

    @pytest.mark.parametrize('length', [0, 1, 125, 126, 65535, 65536])
    def test_the_payload_survives_every_length_encoding(self, length):
        payload = bytes(range(256)) * (length // 256) + b'z' * (length % 256)
        out = ws.ws_encode_frame(payload)
        assert out.endswith(payload) and len(payload) == length

    def test_the_length_is_big_endian(self):
        """The ioctl in the pty module next door is native-endian, and mixing
        the two up is exactly how 80x24 once arrived as 20480x6144."""
        out = ws.ws_encode_frame(b'x' * 300)
        assert out[2:4] == b'\x01\x2c'      # 300, network order

    def test_an_empty_payload_is_a_legal_frame(self):
        assert ws.ws_encode_frame(b'', opcode=0x8) == b'\x88\x00'


class TestReadingClientFrames:
    def read(self, data):
        return ws.ws_read_frame(io.BytesIO(data))

    def test_a_masked_text_frame_is_unmasked(self):
        assert self.read(masked(b'Hello')) == (0x1, b'Hello')

    def test_the_mask_is_applied_per_byte_cycling_over_four(self):
        payload = bytes(range(64))
        assert self.read(masked(payload, opcode=0x2))[1] == payload

    def test_an_unmasked_client_frame_is_still_read(self):
        """Tolerated rather than rejected: real browsers always mask, and the
        looser reader is what the terminal tests drive it with."""
        assert self.read(b'\x81\x02hi') == (0x1, b'hi')

    @pytest.mark.parametrize('length', [0, 1, 125, 126, 1000, 65535, 65536])
    def test_every_length_encoding_round_trips(self, length):
        payload = b'q' * length
        assert self.read(masked(payload, opcode=0x2)) == (0x2, payload)

    def test_a_fragmented_message_is_reassembled(self):
        frames = (masked(b'abc', opcode=0x1, fin=False)
                  + masked(b'def', opcode=0x0, fin=True))
        assert self.read(frames) == (0x1, b'abcdef')

    def test_the_opcode_comes_from_the_first_fragment_not_the_last(self):
        """Continuation frames carry opcode 0. Taking the last one would
        report every fragmented message as a continuation."""
        frames = (masked(b'a', opcode=0x2, fin=False)
                  + masked(b'b', opcode=0x0, fin=True))
        assert self.read(frames)[0] == 0x2

    def test_a_three_way_fragmentation_still_reassembles(self):
        frames = (masked(b'1', opcode=0x1, fin=False)
                  + masked(b'2', opcode=0x0, fin=False)
                  + masked(b'3', opcode=0x0, fin=True))
        assert self.read(frames) == (0x1, b'123')

    def test_a_control_frame_reads_as_itself(self):
        assert self.read(masked(b'', opcode=0x9)) == (0x9, b'')


class TestTheGuardsAgainstAHostileClient:
    def read(self, data):
        return ws.ws_read_frame(io.BytesIO(data))

    def test_an_oversized_frame_is_refused_before_anything_is_allocated(self):
        """The declared length is checked against the cap first. Without that,
        a two-line client makes this box allocate whatever it names."""
        head = b'\x82\xff' + struct.pack('!Q', 1 << 40)
        with pytest.raises(ConnectionError, match='too large'):
            self.read(head)

    def test_the_cap_is_one_megabyte(self):
        over = b'\x82\xff' + struct.pack('!Q', (1 << 20) + 1)
        with pytest.raises(ConnectionError, match='too large'):
            self.read(over)

    def test_a_frame_exactly_at_the_cap_is_not_refused_for_size(self):
        """It fails on the truncated body instead -- proving the boundary is
        inclusive rather than off by one."""
        head = b'\x82\xff' + struct.pack('!Q', 1 << 20)
        with pytest.raises(ConnectionError, match='mid-frame'):
            self.read(head)

    def test_eof_before_a_header_is_a_clean_close(self):
        with pytest.raises(ConnectionError, match='closed'):
            self.read(b'')

    def test_a_one_byte_header_is_a_clean_close(self):
        with pytest.raises(ConnectionError, match='closed'):
            self.read(b'\x81')

    def test_a_body_that_stops_short_is_reported_as_such(self):
        with pytest.raises(ConnectionError, match='mid-frame'):
            self.read(b'\x81\x05he')

    def test_an_unterminated_fragment_stream_does_not_spin(self):
        """No FIN ever arrives; the read must end at EOF rather than loop."""
        with pytest.raises(ConnectionError):
            self.read(masked(b'abc', opcode=0x1, fin=False))


class TestRoundTrip:
    @pytest.mark.parametrize('payload', [
        b'', b'x', b'\x00\xff', b'hello world', bytes(range(256)),
        'héllo wörld'.encode(), b'y' * 70000,
    ])
    def test_what_the_server_encodes_the_reader_can_read_back(self, payload):
        opcode, data = ws.ws_read_frame(io.BytesIO(ws.ws_encode_frame(payload)))
        assert (opcode, data) == (0x2, payload)


class TestServerReExports:
    @pytest.mark.parametrize('name', [
        'ws_accept_key', 'ws_encode_frame', 'ws_read_frame'])
    def test_the_historical_name_is_gone_from_server(self, name):
        """These live in http_app/websocket.py and their only caller is
        http_app/terminal_ws.py — one package away. Routing that through
        `server` was the tax at its most absurd: a name imported into server.py
        so that a sibling module could reach back for it. Round 12 deleted the
        detour."""
        assert getattr(ws, name).__module__ == 'http_app.websocket'
        assert not hasattr(server, name)
