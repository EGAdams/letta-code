"""Provider adapters for bounded receipt-prefill prompts.

Each adapter satisfies the same tiny job: image + prompt -> validated JSON.
Provider authentication and transport stay outside the domain strategies.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
from abc import ABC, abstractmethod
from pathlib import Path

from finance.receipt_prefill_models import (
    FOCUSED_RECEIPT_JSON_SCHEMA,
    GEMINI_FOCUSED_SCHEMA,
    FocusedReceiptReading,
)


def _strip_json_fence(value: str) -> str:
    text = value.strip()
    if not text.startswith('```'):
        return text
    lines = text.splitlines()[1:]
    if lines and lines[-1].strip() == '```':
        lines.pop()
    return '\n'.join(lines).strip()


class IFocusedVisionProvider(ABC):
    @abstractmethod
    def read(self, image_path: Path, prompt: str) -> tuple[FocusedReceiptReading, str]:
        ...


class GeminiFocusedVisionProvider(IFocusedVisionProvider):
    MODEL_NAMES = ('gemini-3.6-flash', 'gemini-flash-latest')

    def read(self, image_path: Path,
             prompt: str) -> tuple[FocusedReceiptReading, str]:
        from dotenv import load_dotenv
        from tools.receipt_scanning_tools.receipt_scanner.backend.services \
            .gemini_rest_client import generate_content

        # The storage CLI loads this same project-owned environment file.
        # Never override a service-provided value.
        load_dotenv(Path.home() / 'rol_finances' / '.env', override=False)
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError('GEMINI_API_KEY environment variable not set')
        image_data = image_path.read_bytes()
        mime_type = mimetypes.guess_type(image_path.name)[0] or 'image/jpeg'
        last_error = None
        for model_name in self.MODEL_NAMES:
            try:
                result = asyncio.run(generate_content(
                    api_key=api_key,
                    model=model_name,
                    prompt=prompt,
                    image_data=image_data,
                    image_mime_type=mime_type,
                    generation_config={
                        'response_mime_type': 'application/json',
                        'response_schema': GEMINI_FOCUSED_SCHEMA,
                        'thinking_config': {'thinking_level': 'minimal'},
                        'max_output_tokens': 512,
                    },
                    timeout=45.0,
                ))
                return FocusedReceiptReading.model_validate_json(
                    result.text), model_name
            except Exception as exc:  # one attempt per Flash model
                last_error = exc
        raise last_error or RuntimeError('Gemini returned no focused reading')


class ClaudeFocusedVisionProvider(IFocusedVisionProvider):
    def read(self, image_path: Path,
             prompt: str) -> tuple[FocusedReceiptReading, str]:
        from tools.receipt_scanning_tools.receipt_scanner.backend.services \
            .claude_oauth_client import generate_content

        model_name = os.getenv(
            'CLAUDE_RECEIPT_MODEL', 'claude-haiku-4-5-20251001')
        image_data = image_path.read_bytes()
        mime_type = mimetypes.guess_type(image_path.name)[0] or 'image/jpeg'
        result = asyncio.run(generate_content(
            model=model_name,
            prompt=prompt,
            image_data=image_data,
            image_mime_type=mime_type,
            max_tokens=300,
            timeout=45.0,
        ))
        return FocusedReceiptReading.model_validate_json(
            _strip_json_fence(result.text)), model_name


class CodexFocusedVisionProvider(IFocusedVisionProvider):
    def read(self, image_path: Path,
             prompt: str) -> tuple[FocusedReceiptReading, str]:
        from tools import codex_cli_vision

        payload = codex_cli_vision.call_vision_json(
            prompt,
            image_path,
            output_schema=FOCUSED_RECEIPT_JSON_SCHEMA,
            timeout=60,
        )
        return FocusedReceiptReading.model_validate(payload), \
            codex_cli_vision.DEFAULT_CODEX_MODEL


PROVIDERS: dict[str, IFocusedVisionProvider] = {
    'gemini-only': GeminiFocusedVisionProvider(),
    'haiku-only': ClaudeFocusedVisionProvider(),
    'codex-only': CodexFocusedVisionProvider(),
}


def read_with_provider(image_path: str, model: str,
                       prompt: str) -> tuple[FocusedReceiptReading, str]:
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f'image does not exist: {path}')
    try:
        provider = PROVIDERS[model]
    except KeyError as exc:
        raise ValueError(f'unsupported focused-read model: {model}') from exc
    return provider.read(path, prompt)
