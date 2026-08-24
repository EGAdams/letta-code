"""Pydantic shapes for the dashboard HTTP layer.

The route ladders in get_routes/post_routes still speak plain dicts (they hand
work straight to server.py's services), but everything the *transport* layer
touches is validated here first. These are the values that arrive from outside
the process — query strings, WebSocket frames, environment — and every one of
them used to be parsed with a bare int()/try-except at the call site.
"""
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Terminal geometry bounds. A browser can send anything; a pty cannot.
MIN_COLS, MAX_COLS, DEFAULT_COLS = 20, 500, 80
MIN_ROWS, MAX_ROWS, DEFAULT_ROWS = 5, 200, 24

NO_CACHE_HEADERS = (
    ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
    ('Pragma', 'no-cache'),
    ('Expires', '0'),
)

_CONTENT_TYPES = {
    'html': 'text/html', 'js': 'application/javascript',
    'css': 'text/css', 'json': 'application/json',
    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
    'pdf': 'application/pdf',
}
DEFAULT_CONTENT_TYPE = 'application/octet-stream'


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


class StaticAsset(BaseModel):
    """A file about to be written to the socket, with its content type resolved."""
    path: str
    content_type: str = ''

    @classmethod
    def resolve(cls, path: str, content_type: str | None = None) -> 'StaticAsset':
        if not content_type:
            ext = path.rsplit('.', 1)[-1].lower()
            content_type = _CONTENT_TYPES.get(ext, DEFAULT_CONTENT_TYPE)
        return cls(path=path, content_type=content_type)


class ErrorResponse(BaseModel):
    """The `{"error": ...}` body every failed dashboard call returns.

    `error` is coerced rather than strictly typed on purpose. This is the
    *error* path: a caller that passes an exception object instead of str(e)
    should still get a well-formed 400 back, not a ValidationError raised from
    inside the error handler. The pre-refactor code was json.dumps, which was
    equally forgiving; keeping that is deliberate, not laziness.
    """
    error: str
    model_config = ConfigDict(extra='forbid')

    @field_validator('error', mode='before')
    @classmethod
    def _coerce_to_text(cls, v: object) -> str:
        return v if isinstance(v, str) else str(v)


class TerminalGeometry(BaseModel):
    """Column/row counts clamped to what a pty will accept."""
    cols: int = DEFAULT_COLS
    rows: int = DEFAULT_ROWS

    @field_validator('cols')
    @classmethod
    def _clamp_cols(cls, v: int) -> int:
        return _clamp(v, MIN_COLS, MAX_COLS)

    @field_validator('rows')
    @classmethod
    def _clamp_rows(cls, v: int) -> int:
        return _clamp(v, MIN_ROWS, MAX_ROWS)


class TerminalSessionRequest(TerminalGeometry):
    """Parsed `GET /api/terminal?agent=&cols=&rows=` query string.

    Fails soft, not closed: a garbled geometry is a cosmetic problem, so it
    falls back to 80x24 rather than refusing the session. A garbled *agent*
    does fail closed — the id is interpolated into an exec, so anything that
    doesn't survive validation in server.py is dropped entirely.
    """
    agent: str = ''

    @classmethod
    def from_query(cls, query: dict[str, list[str]]) -> 'TerminalSessionRequest':
        def one(key: str, default: str) -> str:
            return (query.get(key) or [default])[0] or default
        try:
            return cls(agent=one('agent', ''),
                       cols=int(one('cols', str(DEFAULT_COLS))),
                       rows=int(one('rows', str(DEFAULT_ROWS))))
        except (TypeError, ValueError):
            return cls(agent=one('agent', ''))


class TerminalResizeFrame(TerminalGeometry):
    """A browser `{"t":"r","c":<cols>,"r":<rows>}` frame."""

    @classmethod
    def from_frame(cls, msg: dict, fallback: TerminalGeometry) -> 'TerminalGeometry':
        try:
            return cls(cols=int(msg.get('c', fallback.cols)),
                       rows=int(msg.get('r', fallback.rows)))
        except (TypeError, ValueError):
            return fallback


class BackgroundTask(BaseModel):
    """A daemon thread started at boot, plus the banner line it prints.

    Modelled so the startup sequence is a list of declared tasks instead of a
    dozen copy-pasted Thread(...)/print(...) pairs in __main__.
    """
    label: str
    target: Callable[[], object]
    banner: str = ''
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ServerConfig(BaseModel):
    """Where the dashboard listens."""
    host: str = '0.0.0.0'
    port: int = Field(default=8765, ge=1, le=65535)
    scheme: Literal['http'] = 'http'

    @property
    def url(self) -> str:
        return f'{self.scheme}://localhost:{self.port}/'

    @property
    def address(self) -> tuple[str, int]:
        return (self.host, self.port)
