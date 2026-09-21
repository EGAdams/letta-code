"""Observer implementations for voice latency and fallback events."""


class NullVoiceTimingObserver:
    def observe(self, stage: str, duration_seconds: float) -> None:
        pass


class LoggingVoiceTimingObserver:
    def __init__(self, writer=None):
        self._writer = writer or (lambda message: print(message, flush=True))

    def observe(self, stage: str, duration_seconds: float) -> None:
        self._writer(
            f"[voice-pipeline] stage={stage} "
            f"duration_ms={duration_seconds * 1000:.1f}"
        )


class NullSttFallbackObserver:
    def observe(self, error: Exception) -> None:
        pass


class LoggingSttFallbackObserver:
    def __init__(self, writer=None):
        self._writer = writer or (lambda message: print(message, flush=True))

    def observe(self, error: Exception) -> None:
        self._writer(
            f"[voice-pipeline] groq_failed={type(error).__name__}; "
            "using_local_whisper=true"
        )
