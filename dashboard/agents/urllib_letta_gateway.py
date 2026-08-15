"""urllib adapter for the Letta agent gateway port."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import quote

from agents.letta_gateway import ILettaGateway, LettaAgentMessage, LettaAgentModel


def _decode_json(raw: bytes | str) -> object:
    return cast(object, json.loads(raw))


def _string_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        return None
    return cast(dict[str, object], mapping)


def _object_list(value: object) -> list[object] | None:
    if not isinstance(value, list):
        return None
    return cast(list[object], value)


def _content_text(parts: list[object]) -> str:
    texts: list[str] = []
    for part in parts:
        part_dict = _string_dict(part)
        if part_dict is None:
            continue
        text = part_dict.get('text', '')
        if isinstance(text, str):
            texts.append(text)
    return ' '.join(texts)


def _approval_names(calls: list[object]) -> tuple[str, ...]:
    names: list[str] = []
    for call in calls:
        call_dict = _string_dict(call)
        if call_dict is None:
            continue
        name = call_dict.get('name', '?')
        if isinstance(name, str):
            names.append(name)
    return tuple(names)


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
                payload = _string_dict(_decode_json(response.read()))
            if payload is None:
                return None
            llm_config: object = payload.get('llm_config')
            if llm_config is None:
                llm_config = dict[str, object]()
            llm_config = _string_dict(llm_config)
            if llm_config is None:
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

    def get_agent_messages(
        self,
        agent_id: str,
        *,
        limit: int = 200,
        timeout: float = 25,
    ) -> tuple[LettaAgentMessage, ...]:
        if not agent_id or isinstance(limit, bool) or limit < 1:
            return ()
        url = (
            f'{self._base_url}/v1/agents/{quote(agent_id, safe="")}'
            f'/messages?limit={limit}'
        )
        try:
            with self._opener(url, timeout=timeout) as response:
                payload = _decode_json(response.read())
            envelope = _string_dict(payload)
            if envelope is not None:
                payload = envelope.get('messages', envelope.get('results'))
            messages = _object_list(payload)
            if messages is None:
                return ()
            normalized = tuple(self._normalize_message(item) for item in messages)
            if any(message is None for message in normalized):
                return ()
            return tuple(message for message in normalized if message is not None)
        except Exception:
            return ()

    @staticmethod
    def _normalize_message(payload: object) -> LettaAgentMessage | None:
        message = _string_dict(payload)
        if message is None:
            return None
        message_type = message.get('message_type', '')
        created_at = message.get('created_at', '')
        date = message.get('date', '')
        if not isinstance(message_type, str):
            return None
        if not isinstance(created_at, str):
            return None
        if not isinstance(date, str):
            return None

        content = message.get('content', '')
        content_parts = _object_list(content)
        if content_parts is not None:
            content = _content_text(content_parts)
        elif not isinstance(content, str):
            content = str(content)

        tool_call_name = ''
        tool_call_arguments: tuple[tuple[str, str], ...] = ()
        tool_call = message.get('tool_call')
        if tool_call is not None:
            tool_call_dict = _string_dict(tool_call)
            if tool_call_dict is None:
                return None
            name = tool_call_dict.get('name', '')
            if not isinstance(name, str):
                return None
            tool_call_name = name
            arguments: object = tool_call_dict.get('arguments')
            if arguments is None:
                arguments = dict[str, object]()
            if isinstance(arguments, str):
                try:
                    arguments = _decode_json(arguments)
                except Exception:
                    arguments = {}
            argument_dict = _string_dict(arguments)
            if argument_dict is not None:
                tool_call_arguments = tuple(
                    (key, str(value)) for key, value in argument_dict.items()
                )

        tool_return = message.get('tool_return', '')
        tool_return_dict = _string_dict(tool_return)
        if tool_return_dict is not None:
            tool_return = tool_return_dict.get('content', '')
        if not isinstance(tool_return, str):
            tool_return = str(tool_return)

        approval_tool_names: tuple[str, ...] = ()
        tool_calls = message.get('tool_calls')
        if tool_calls is not None:
            calls = _object_list(tool_calls)
            if calls is None:
                return None
            approval_tool_names = _approval_names(calls)

        reasoning = message.get('reasoning', '')
        if not isinstance(reasoning, str):
            reasoning = str(reasoning)

        return LettaAgentMessage(
            message_type=message_type,
            created_at=created_at,
            date=date,
            content=content,
            tool_call_name=tool_call_name,
            tool_call_arguments=tool_call_arguments,
            tool_return=tool_return,
            approval_tool_names=approval_tool_names,
            reasoning=reasoning,
        )
