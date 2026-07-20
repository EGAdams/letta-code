"""Configuration for the Agents-home router (voice/text -> agent detection)."""
import os

from voice import config as voice_config

LETTA_BASE_URL = voice_config.LETTA_BASE_URL

# The Letta agent that performs name detection. Same "small, fast, history
# cleared every call" pattern as voice.config's transcript-cleanup-agent.
ROUTER_AGENT_ID = os.environ.get("ROUTER_AGENT_ID")  # if None, resolve by name
ROUTER_AGENT_NAME = os.environ.get("ROUTER_AGENT_NAME", "dashboard-agent-router")

# Only the top-level roster is routable from this page (not Mazda's/Suzuki's
# sub-agents, which voice.config.KNOWN_AGENT_NAMES also includes).
ROUTER_AGENT_NAMES = [
    "Frita",
    "Scissari",
    "Hailey",
    "Jeri",
    "Mazda",
    "Suzuki",
]
