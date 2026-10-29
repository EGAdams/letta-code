"""The response and port used by the same-origin documentation gateway."""
from typing import Protocol

from pydantic import BaseModel, Field


class DocumentationResponse(BaseModel):
    status: int = Field(ge=100, le=599)
    body: bytes
    content_type: str = 'application/octet-stream'


class DocumentationUpstream(Protocol):
    def fetch(self, method: str, target: str, body: bytes | None,
              content_type: str) -> DocumentationResponse: ...
