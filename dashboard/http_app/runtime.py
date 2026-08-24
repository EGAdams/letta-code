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
