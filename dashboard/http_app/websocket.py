"""The RFC 6455 wire format, by hand.

The dashboard is stdlib-only on purpose, so the handshake and framing are
implemented here instead of pulling in `websockets`. That is a small amount of
bit-twiddling with a large blast radius: a browser drops the connection without
explanation on any protocol violation, and the symptom is a terminal panel that
goes blank with nothing in any log.

Three things in here are load-bearing and easy to get wrong:

  * client frames are masked, server frames must not be;
  * a message can arrive fragmented, with the opcode only on the first frame;
  * the length field has three encodings, and the two-byte one is big-endian
    where the ioctl in the pty module next door is native-endian.

All of it is pure, so it is tested against byte literals rather than a socket.
"""

from __future__ import annotations

import base64
import hashlib
import struct

_WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def ws_accept_key(sec_websocket_key):
    """Sec-WebSocket-Accept value for a client's Sec-WebSocket-Key (RFC 6455 §4.2.2)."""
    digest = hashlib.sha1((sec_websocket_key + _WS_GUID).encode('ascii')).digest()
    return base64.b64encode(digest).decode('ascii')


def ws_encode_frame(payload, opcode=0x2):
    """Encode one unmasked (server→client) WebSocket frame, FIN set."""
    head = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        head += bytes([n])
    elif n < 65536:
        head += bytes([126]) + struct.pack('!H', n)
    else:
        head += bytes([127]) + struct.pack('!Q', n)
    return head + payload


def ws_read_frame(rfile):
    """Read one client→server frame from a blocking file object.

    Returns (opcode, payload:bytes) with client masking removed and fragmented
    messages reassembled. Raises ConnectionError on EOF/protocol violation.
    """
    opcode = None
    payload = b''
    while True:
        head = rfile.read(2)
        if len(head) < 2:
            raise ConnectionError('websocket closed')
        fin = head[0] & 0x80
        op = head[0] & 0x0F
        masked = head[1] & 0x80
        n = head[1] & 0x7F
        if n == 126:
            n = struct.unpack('!H', rfile.read(2))[0]
        elif n == 127:
            n = struct.unpack('!Q', rfile.read(8))[0]
        if n > 1 << 20:
            raise ConnectionError('websocket frame too large')
        mask = rfile.read(4) if masked else b''
        data = rfile.read(n)
        if len(data) < n:
            raise ConnectionError('websocket closed mid-frame')
        if masked:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if op != 0:               # first (or only) fragment carries the opcode
            opcode = op
        payload += data
        if fin:
            return opcode, payload
