# Error Shapes Reference

## Run Metadata Error Structures

### Doubly-nested (most common from Letta 0.16.3 streaming)

```json
{
  "error": {
    "error": {
      "message_type": "error_message",
      "run_id": "run-xxxxxxxx",
      "error_type": "internal_error",
      "message": "An unknown error occurred with the LLM streaming request.",
      "detail": "CONFLICT: Cannot send a new message: The agent is waiting for approval...",
      "seq_id": null
    },
    "run_id": "run-xxxxxxxx"
  }
}
```

`fetchRunErrorDetail` extracts `.error.detail` → `"CONFLICT: ..."` ✓

### Flat (direct error metadata)

```json
{
  "error_type": "llm_error",
  "message": "ChatGPT API error: ...",
  "detail": "INTERNAL_SERVER_ERROR: ChatGPT request failed with status 'response.incomplete'"
}
```

`fetchRunErrorDetail` extracts `.detail` directly ✓

## Stream Chunk Error Shapes

### LettaErrorMessage (mid-stream, `message_type: "error_message"`)

```json
{
  "message_type": "error_message",
  "run_id": "run-xxxxxxxx",
  "error_type": "internal_error",
  "message": "An error occurred during agent execution.",
  "detail": "INTERNAL_SERVER_ERROR: ChatGPT request failed with status 'response.incomplete'",
  "seq_id": 5
}
```

Handled in `streamProcessor.ts` → `errorInfo.detail`.

### Pre-stream APIError (409 Conflict)

Thrown as `APIError` before any stream chunks. Handled via `extractConflictDetail` in `turn-recovery-policy.ts`.

## Error Type Meanings

| `error_type` | Meaning | Default retry? |
|---|---|---|
| `llm_error` | Provider returned an error | Yes (if retryable pattern matches) |
| `internal_error` | Letta server internal error | Only if detail matches retryable pattern |
| `agent_error` | Agent logic error | No |

## Key Pattern Lists (turn-recovery-policy.ts)

### RETRYABLE_PROVIDER_DETAIL_PATTERNS
Partial string matches against the error detail. Add new strings here when a provider error should be silently retried.

Current entries include: `"Anthropic API error"`, `"OpenAI API error"`, `"ChatGPT API error"`, `"ChatGPT server error"`, `"ChatGPT request failed"`, `"Connection error"`, `"upstream connect error"`, `"overloaded"`, etc.

### NON_RETRYABLE_PROVIDER_DETAIL_PATTERNS
Auth/quota errors that should NOT be retried: `"invalid api key"`, `"context_length_exceeded"`, `"invalid_request_error"`, etc.
