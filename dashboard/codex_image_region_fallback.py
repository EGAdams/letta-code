"""Codex CLI adapter for the image-region fallback annotation port."""

import json
import os
import shutil
import subprocess

from document_annotation_contracts import (
    ExpenseEvidence,
    IImageRegionFallbackMatcher,
    ImageRegionMatch,
)


class CodexCliImageRegionFallbackMatcher(IImageRegionFallbackMatcher):
    """Ask subscription-backed Codex vision for one payment-region box."""

    def __init__(
        self,
        codex_path: str | None = None,
        model: str | None = None,
        timeout: float = 120,
        runner=None,
    ) -> None:
        self._codex_path = (
            codex_path
            or shutil.which("codex")
            or os.path.expanduser("~/.npm-global/bin/codex")
        )
        self._model = model or os.environ.get(
            "DOCUMENT_ANNOTATION_FALLBACK_MODEL",
            "gpt-5.6-luna",
        )
        self._timeout = timeout
        self._runner = runner or subprocess.run

    def find_region(
        self,
        source_path: str,
        evidence: ExpenseEvidence,
    ) -> ImageRegionMatch | None:
        prompt = (
            "Inspect only the attached supporting-document image. Find the single "
            "compact source payment region for this expense:\n"
            f"date: {evidence.expense_date}\n"
            f"amount: {evidence.amount}\n"
            f"description/payee: {evidence.description}\n"
            f"vendor key: {evidence.vendor_key}\n"
            "For a check image, select the check face containing the payment and "
            "payee. Exclude endorsement, back-office, remote-deposit, posting, "
            "summary, and unrelated regions. Coordinates must use original image "
            "pixels. If there is no confident unique match, return no regions. "
            "Return only JSON in this exact shape: "
            '{"confidence":0.0,"regions":['
            '{"left":0,"top":0,"right":0,"bottom":0}]}'
        )
        command = [
            self._codex_path,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--model",
            self._model,
            "--image",
            source_path,
            "-",
        ]
        completed = self._runner(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown error").strip()
            raise RuntimeError(f"Codex image matching failed: {detail}")
        payload = self._parse_payload(completed.stdout)
        regions = payload.get("regions")
        if not isinstance(regions, list) or len(regions) != 1:
            return None
        confidence = payload.get("confidence")
        region = regions[0]
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not isinstance(region, dict)
        ):
            raise ValueError("Codex image matching returned an invalid result")
        try:
            bounds = tuple(
                float(region[key])
                for key in ("left", "top", "right", "bottom")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "Codex image matching returned invalid bounds"
            ) from exc
        return ImageRegionMatch(
            region=bounds,
            confidence=float(confidence),
        )

    @staticmethod
    def _parse_payload(output: str) -> dict:
        decoder = json.JSONDecoder()
        for index, character in enumerate(str(output or "")):
            if character != "{":
                continue
            try:
                payload, _end = decoder.raw_decode(output[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise ValueError("Codex image matching returned no JSON object")
