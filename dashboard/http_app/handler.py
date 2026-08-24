"""The dashboard's request handler, composed from its four seams.

`DashboardHandler` used to be a single 1,380-line class in server.py. Nothing
about its behaviour changed here — it was split along the seams that were
already implicit in it:

    HttpTransportMixin       how bytes leave the socket
    TerminalWebSocketMixin   the one request that becomes a long-lived socket
    GetRoutesMixin           the read-side route ladder  (do_GET)
    PostRoutesMixin          the write-side route ladder (do_POST)

MRO order matters: the route mixins call into transport helpers, so transport
sits after them and SimpleHTTPRequestHandler last (it supplies send_response,
send_header, and the static-file fallback both ladders delegate to).
"""
from http.server import SimpleHTTPRequestHandler

from .get_routes import GetRoutesMixin
from .post_routes import PostRoutesMixin
from .terminal_ws import TerminalWebSocketMixin
from .transport import HttpTransportMixin


class DashboardHandler(
    GetRoutesMixin,
    PostRoutesMixin,
    TerminalWebSocketMixin,
    HttpTransportMixin,
    SimpleHTTPRequestHandler,
):
    """Serves dashboard.html plus the /api/* surface. See the mixins for routes."""
