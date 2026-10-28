"""The one IVoiceMediaAdmission both route ladders ask.

Composition only: this is where Sydney is named as sharing Toyota's voice
pilot, so neither get_routes nor post_routes compares agent ids itself.
"""
import sydney_service
from voice.media_admission import IVoiceMediaAdmission, PilotAgentAdmission

VOICE_MEDIA: IVoiceMediaAdmission = PilotAgentAdmission(
    sharing_agent_ids=(sydney_service.SYDNEY_AGENT_ID,),
)
