"""Boot: the socket server and the declared startup sequence.

Kept free of any `server` import so this module can be read (and tested) on its
own — server.py hands it a handler class and a list of BackgroundTask models.
"""
import threading
from http.server import ThreadingHTTPServer

from .models import BackgroundTask, ServerConfig


class ReusableHTTPServer(ThreadingHTTPServer):
    """Threaded so a slow request (whisper is ~5s) can't block the pollers."""
    allow_reuse_address = True
    daemon_threads = True

    # A handler that never finishes a blocking read/write leaves its thread
    # and socket stuck forever -- observed in production as 381 live handler
    # threads and 269+ sockets stuck in CLOSE-WAIT after a few hours, which
    # eventually fails every new request with "Too many open files" once the
    # process hits its fd ulimit. Bounding every connection's blocking I/O
    # guarantees finish_request() always returns -- raising socket.timeout is
    # fine, BaseServer's `finally: self.shutdown_request(request)` still runs
    # and reclaims the fd -- so a wedged request just times out instead of
    # leaking. /api/terminal is the one legitimately long-lived connection; it
    # opts out by clearing its own socket's timeout right after the WebSocket
    # upgrade (see terminal_ws.py).
    request_socket_timeout = 120

    def finish_request(self, request, client_address):
        request.settimeout(self.request_socket_timeout)
        super().finish_request(request, client_address)


def start_background_tasks(tasks):
    """Start each declared daemon thread and print its banner, in order."""
    for task in tasks:
        threading.Thread(target=task.target, daemon=True, name=task.label).start()
        if task.banner:
            print(task.banner)


def serve(handler_class, config=None, tasks=(), banners=()):
    """Bind, announce, start the background threads, then serve until Ctrl-C."""
    config = config or ServerConfig()
    httpd = ReusableHTTPServer(config.address, handler_class)
    print(f'Dashboard server on {config.url}')
    for line in banners:
        print(line)
    start_background_tasks(tasks)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    return httpd
