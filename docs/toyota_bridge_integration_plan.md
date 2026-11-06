# Toyota Star Trek Bridge integration plan

## Finding

Toyota is present in this checkout, but the Star Trek Bridge task producer and
queue are not. Toyota's existing integration is the receptionist sidecar:

- `dashboard/toyota_service.py` exposes `IReceptionistSidecar` through the
  shared `receptionist_sidecar.SidecarBridge`.
- `dashboard/http_app/post_routes.py` routes Toyota turns to that sidecar (or
  the existing Letta fallback).
- `dashboard/monitoring/worker_activity.py` is deliberately read-only. It
  states that this dashboard owns no `StarTrekBridge`/Codex task ledger and
  returns an unavailable state when `WORKER_ACTIVITY_SNAPSHOT` is absent.
- `dashboard/scan_jobs/` is a separate, authenticated scanner façade; its
  scopes and job contract are not a Star Trek task contract.

Therefore no submit/status/result adapter is implemented here. There is no
existing task endpoint, authenticated client, durable task identifier, or
worker queue to wrap. Adding one would claim operational connectivity that
this workspace does not have.

## Required wiring in Toyota's owner repository

The repository that owns `StarTrekBridge`/the worker queue should provide a
small authenticated HTTP API (or an equivalent injected transport) with these
operations:

```text
submit(request) -> {task_id, status: "queued"}
status(task_id) -> {
  task_id,
  status: "queued" | "running" | "completed" | "failed",
  error?: string
}
result(task_id) -> {
  task_id,
  status: "completed",
  result: JSON value
}
```

Recommended request shape:

```json
{
  "request_id": "caller-supplied idempotency key",
  "agent": "Toyota",
  "task": "the requested Bridge task",
  "metadata": {}
}
```

The client contract should be an interface/port, not a Toyota-specific
implementation:

```python
class BridgeTaskClient(Protocol):
    def submit(self, request: BridgeTaskRequest) -> BridgeTaskRef: ...
    def status(self, task_id: str) -> BridgeTaskStatus: ...
    def result(self, task_id: str) -> BridgeTaskResult: ...
```

The concrete HTTP adapter should accept an injected transport and base URL,
use the owner's existing bearer-token configuration, validate every response,
and never embed credentials. It should preserve `queued` as a normal state,
return a typed not-ready result for `queued`/`running`, and surface transport,
HTTP, malformed-response, and worker `failed` errors distinctly.

## Toyota integration changes

After the owner repository exposes the contract, wire it at Toyota's
composition boundary rather than inside `SidecarBridge`:

1. Add the shared request/reference/status/result models and the
   `BridgeTaskClient` port in the owner repository.
2. Add its HTTP implementation with an injected stub transport.
3. Inject that client into Toyota's receptionist command/intent handler.
4. Map a receptionist request to `submit`, retain the returned `task_id`, and
   expose polling and result retrieval to the existing Toyota response path.
5. Keep the current sidecar/Letta conversation path unchanged for ordinary
   turns and fail closed when the Bridge service is unavailable.
6. If the UI needs visibility, extend the existing worker activity read model;
   do not infer task state from systemd health or an empty snapshot.

## Required tests

The owner repository should add unit tests using a stub transport for:

- submit: request shape, idempotency key, authentication injection, and
  returned `task_id`/`queued` state;
- status: `queued`, `running`, `completed`, and `failed` payloads;
- result: completed result retrieval and rejection of a not-ready result;
- HTTP errors, transport errors, malformed JSON/schema, missing task IDs, and
  worker-reported failures;
- no credentials in logs or request bodies beyond the authorization header.

Add one Toyota handler test proving that a Bridge request submits once and
that a queued task is reported as queued, not fabricated as complete.

## Current blocker

The worker queue and task ledger are outside this allowed workspace and are not
exposed here as a callable API. Until their owner supplies the authenticated
submit/status/result contract above, Toyota cannot safely submit or retrieve
Star Trek Bridge tasks from this repository.
