"""Voice input for the dashboard: record -> whisper.cpp -> Letta cleanup -> send.

Wiring (Factory) lives in build_transcriber() / build_cleanup() / build_pipeline().
"""
from .pipeline import VoicePipeline, build_pipeline, handle_voice_upload

__all__ = ["VoicePipeline", "build_pipeline", "handle_voice_upload"]
