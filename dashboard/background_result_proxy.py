"""Non-blocking proxy for slow, refreshable values."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class BackgroundResultProxy(BaseModel):
    """Serve the last value while one shared background refresh runs."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    loader: Callable[..., Any]
    max_workers: int = Field(default=2, ge=1)
    refresh_seconds: float = Field(default=0, ge=0)
    name: str = Field(default='refresh', min_length=1)
    _executor: ThreadPoolExecutor = PrivateAttr()
    _entries: dict[Any, dict[str, Any]] = PrivateAttr(default_factory=dict)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def model_post_init(self, __context: Any) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix=self.name)

    def get(self, key, *loader_args, default=None):
        now = time.time()
        with self._lock:
            entry = self._entries.setdefault(
                key, {'value': default, 'fetched_at': 0, 'future': None})
            future = entry['future']
            if ((future is None or future.done())
                    and now - entry['fetched_at'] >= self.refresh_seconds):
                entry['future'] = self._executor.submit(
                    self._refresh, key, loader_args)
            return entry['value']

    def _refresh(self, key, loader_args):
        try:
            value = self.loader(*loader_args)
        except Exception as exc:
            print(f'[{self.name}] refresh failed: {exc}')
            value = None
        with self._lock:
            entry = self._entries[key]
            if value is not None:
                entry['value'] = value
                entry['fetched_at'] = time.time()
            entry['future'] = None
