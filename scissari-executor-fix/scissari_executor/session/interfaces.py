"""Ports / interfaces for the session layer (F7) — program to THESE."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import StreamEventKind, SessionVerdict, TransportInfo


class ISessionHealth(ABC):
    """State machine: is the agent actually hung, or just mid-tool-call?"""

    @abstractmethod
    def on_event(self, kind: StreamEventKind, at: Optional[float] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def should_close(self, at: Optional[float] = None) -> SessionVerdict:
        raise NotImplementedError

    @abstractmethod
    def reset(self, at: Optional[float] = None) -> None:
        raise NotImplementedError


class IKeepalive(ABC):
    """Observer over health: keep the session warm while a tool call runs."""

    @abstractmethod
    def is_suppressed(self) -> bool:
        """True while an inactivity-timer suppression is in effect."""
        raise NotImplementedError

    @abstractmethod
    def next_deadline(self, at: Optional[float] = None) -> float:
        """Absolute timestamp the next close-check should fire."""
        raise NotImplementedError


class ISubprocessTransport(ABC):
    """The raw SDK SubprocessTransport (Node side). Adapter target."""

    @property
    @abstractmethod
    def info(self) -> TransportInfo:
        raise NotImplementedError

    @abstractmethod
    def spawn(self) -> None:
        """(Re)start the subprocess. STUB."""
        raise NotImplementedError

    @abstractmethod
    def send(self, data: str) -> None:
        """Raw send; throws 'Transport not connected' when dead. STUB."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class IResilientTransport(ABC):
    """Proxy/Decorator over ISubprocessTransport that re-spawns on dead send()."""

    @abstractmethod
    async def send(self, data: str) -> None:
        raise NotImplementedError


class ISessionSupervisor(ABC):
    """Facade the bot + heartbeat call instead of the raw SDK session."""

    @abstractmethod
    def feed_event(self, kind: StreamEventKind, at: Optional[float] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def tick(self, at: Optional[float] = None) -> SessionVerdict:
        raise NotImplementedError

    @abstractmethod
    async def send(self, data: str) -> None:
        raise NotImplementedError
