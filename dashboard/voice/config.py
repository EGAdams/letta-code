"""Configuration for the voice pipeline.

Defaults mirror lettabot's working whisper.cpp setup so the dashboard reuses the
exact binary/model/ffmpeg it already trusts. Everything is overridable via env.
"""
import os

HOME = os.path.expanduser("~")

# ── whisper.cpp (speech-to-text) ──────────────────────────────────────────────
WHISPER_CPP_BIN = os.environ.get(
    "WHISPER_CPP_BIN", os.path.join(HOME, "whisper.cpp", "build", "bin", "whisper-cli")
)
DEFAULT_WHISPER_MODEL_PATH = os.path.join(
    HOME, "whisper.cpp", "models", "ggml-base.en.bin"
)
WHISPER_MODEL_PATH = os.environ.get(
    "WHISPER_MODEL_PATH", DEFAULT_WHISPER_MODEL_PATH
)
# No system ffmpeg on this host — fall back to lettabot's bundled imageio-ffmpeg.
FFMPEG_BIN = os.environ.get(
    "FFMPEG_BIN",
    os.path.join(
        HOME, "lettabot", ".venv_ffmpeg", "lib", "python3.12", "site-packages",
        "imageio_ffmpeg", "binaries", "ffmpeg-linux-x86_64-v7.0.2",
    ),
)
WHISPER_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "auto")
_threads = os.environ.get("WHISPER_THREADS")
WHISPER_THREADS = int(_threads) if _threads and _threads.isdigit() else None

# ── Letta cleanup agent ───────────────────────────────────────────────────────
LETTA_BASE_URL = os.environ.get("LETTA_BASE_URL", "http://100.80.49.10:8283").rstrip("/")
CLEANUP_AGENT_ID = os.environ.get("CLEANUP_AGENT_ID")  # if None, resolve by name
CLEANUP_AGENT_NAME = os.environ.get("CLEANUP_AGENT_NAME", "transcript-cleanup-agent")
CLEANUP_MODEL = os.environ.get("CLEANUP_MODEL", "gemini-2.5-flash-lite")

# Known agent names fed to the cleanup model so it can fix mishears (Friday -> Frita).
# Kept in sync with LETTA_AGENTS in server.py.
KNOWN_AGENT_NAMES = [
    "Scissari",
    "Frita",
    "Hailey",
    "Jeri",
    "Mazda",
    "Mazda Router",
    "Mazda Parser",
    "Mazda Vendor Identity",
    "Mazda Receipt Linker",
    "Mazda Categorization",
    "Suzuki",
    "Suzuki Router",
    "Suzuki Reproducer",
    "Suzuki Static Analysis",
    "Suzuki Patcher",
    "Suzuki Test Runner",
    "Suzuki Regression",
]

# Initial prompt that biases whisper.cpp toward the real agent names, so e.g.
# "Mazda" isn't transcribed as the common English name "Melissa" in the first place.
WHISPER_PROMPT = os.environ.get(
    "WHISPER_PROMPT", "Agent names: " + ", ".join(KNOWN_AGENT_NAMES) + "."
)
