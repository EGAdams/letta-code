"""urllib adapter for the Letta agent gateway port."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from agents.letta_gateway import ILettaGateway, LettaAgentModel


class UrllibLettaGateway(ILettaGateway):
    def __init__(
        self,
        base_url: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        normalized = str(base_url or '').rstrip('/')
        if not normalized:
            raise ValueError('base_url cannot be blank')
        self._base_url = normalized
        self._opener = opener

    def get_agent_model(
        self,
        agent_id: str,
        *,
        timeout: float = 15,
    ) -> LettaAgentModel | None:
        if not agent_id:
            return None
        url = f'{self._base_url}/v1/agents/{quote(agent_id, safe="")}'
        try:
            with self._opener(url, timeout=timeout) as response:
                payload = json.loads(response.read().decode())
            if not isinstance(payload, dict):
                return None
            llm_config = payload.get('llm_config') or {}
            if not isinstance(llm_config, dict):
                return None
            handle = llm_config.get('handle')
            model = llm_config.get('model')
            if handle is not None and not isinstance(handle, str):
                return None
            if model is not None and not isinstance(model, str):
                return None
            return LettaAgentModel(current=handle or model or '')
        except Exception:
            return None
