"""The dashboard's HTTP layer, lifted out of server.py.

Deliberately *not* re-exporting DashboardHandler here: the handler mixins do
`import server`, and server.py imports this package from its own tail. Keeping
__init__ free of that dependency means importing http_app.models or
http_app.runtime never drags server.py in, and no import cycle can form.
Import the handler explicitly:

    from http_app.handler import DashboardHandler
"""
from .models import BackgroundTask, ErrorResponse, ServerConfig, StaticAsset
from .runtime import ReusableHTTPServer, serve, start_background_tasks

__all__ = [
    'BackgroundTask', 'ErrorResponse', 'ServerConfig', 'StaticAsset',
    'ReusableHTTPServer', 'serve', 'start_background_tasks',
]
