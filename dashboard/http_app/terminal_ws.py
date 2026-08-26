"""GET /api/terminal: the RFC 6455 upgrade + pty bridge (transport seam).

Split out from the route ladders because this is the one request that stops
being a request: after the 101 the handler thread owns a socket for minutes.
Query params and browser resize frames are untrusted input, so both are
validated through the Pydantic models in .models rather than ad-hoc int() calls.
"""
import fcntl
import json
import os
import struct
import termios
import threading

from letta_ids import _TERMINAL_ID_RE
from terminal.pty_session import _terminal_reap, _terminal_spawn_shell

from . import services as srv

from .models import TerminalResizeFrame, TerminalSessionRequest
from .websocket import ws_accept_key, ws_encode_frame, ws_read_frame


class TerminalWebSocketMixin:
    def handle_terminal_ws(self, query):
        """Upgrade GET /api/terminal to a WebSocket and bridge it to a pty shell."""
        key = self.headers.get('Sec-WebSocket-Key')
        upgrade = (self.headers.get('Upgrade') or '').lower()
        if not key or upgrade != 'websocket':
            return self.error_response('expected a websocket upgrade', 400)

        request = TerminalSessionRequest.from_query(query)
        letta_agent_id = ''
        if request.agent:
            lid = srv.letta_id_for(request.agent)
            # letta_id_for returns the id as-is for Letta agents; guard the exec.
            if lid and _TERMINAL_ID_RE.match(lid):
                letta_agent_id = lid
        cols, rows = request.cols, request.rows

        # Write the 101 by hand: a WebSocket upgrade must be HTTP/1.1, but this
        # handler's protocol_version is HTTP/1.0 (send_response would emit the
        # wrong status line and browsers would reject the upgrade). We also skip
        # the default Server/Date headers to keep the handshake minimal.
        handshake = (
            'HTTP/1.1 101 Switching Protocols\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Accept: {ws_accept_key(key)}\r\n\r\n'
        )
        try:
            self.wfile.write(handshake.encode('ascii'))
            self.wfile.flush()
        except OSError:
            return

        sock = self.connection
        pid, master_fd = _terminal_spawn_shell(cols, rows, letta_agent_id)
        alive = threading.Event()
        alive.set()

        def pump_browser_to_pty():
            """Reader thread: browser frames → pty (input, resize, close)."""
            try:
                while alive.is_set():
                    opcode, data = ws_read_frame(self.rfile)
                    if opcode == 0x8:              # close
                        break
                    if opcode == 0x9:              # ping → pong
                        try:
                            sock.sendall(ws_encode_frame(data, opcode=0xA))
                        except OSError:
                            break
                        continue
                    if opcode not in (0x1, 0x2):   # ignore pong/other
                        continue
                    try:
                        msg = json.loads(data.decode('utf-8', 'ignore'))
                    except ValueError:
                        continue
                    if msg.get('t') == 'i':
                        os.write(master_fd, str(msg.get('d', '')).encode('utf-8'))
                    elif msg.get('t') == 'r':
                        size = TerminalResizeFrame.from_frame(msg, request)
                        # Native byte order (see _terminal_spawn_shell): the
                        # WebSocket frame lengths above are big-endian per RFC
                        # 6455, but a struct winsize is not a wire format.
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
                                    struct.pack('HHHH', size.rows, size.cols, 0, 0))
            except (ConnectionError, OSError, ValueError):
                pass
            finally:
                alive.clear()

        reader = threading.Thread(target=pump_browser_to_pty, daemon=True)
        reader.start()

        # Handler thread: pty output → browser, until either side closes.
        import select as _select
        try:
            while alive.is_set():
                ready, _w, _e = _select.select([master_fd], [], [], 0.25)
                if not ready:
                    continue
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                try:
                    sock.sendall(ws_encode_frame(chunk, opcode=0x2))
                except OSError:
                    break
        finally:
            alive.clear()
            try:
                sock.sendall(ws_encode_frame(b'', opcode=0x8))
            except OSError:
                pass
            try:
                os.close(master_fd)
            except OSError:
                pass
            _terminal_reap(pid)
