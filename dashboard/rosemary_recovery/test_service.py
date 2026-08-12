from __future__ import annotations

import http.client
import threading
from unittest.mock import patch

from . import service


def test_operations_are_allowlisted() -> None:
    assert set(service.OPERATIONS) == {
        "status",
        "start_keepalive",
        "restart_wsl_tailscale",
        "reauth_instructions",
        "verify_recovery",
    }


def test_start_keepalive_uses_fixed_task_arguments() -> None:
    with patch.object(
        service,
        "_run",
        return_value={"ok": True, "returncode": 0, "stdout": "", "stderr": ""},
    ) as run:
        result = service.start_keepalive()
    assert result["ok"] is True
    assert run.call_args.args[0] == [
        service._exe("schtasks.exe"),
        "/run",
        "/tn",
        service.KEEPALIVE_TASK,
    ]


def test_reauth_never_executes_a_command() -> None:
    with patch.object(service, "_run") as run:
        result = service.reauth_instructions()
    assert result["requires_local_interaction"] is True
    run.assert_not_called()


def _request(
    path: str, *, method: str = "GET", token: str | None = None
) -> tuple[int, str]:
    server = service.ThreadingHTTPServer(("127.0.0.1", 0), service.RecoveryHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    connection = http.client.HTTPConnection(*server.server_address, timeout=2)
    connection.request(method, path, headers=headers)
    response = connection.getresponse()
    result = response.status, response.read().decode()
    connection.close()
    thread.join(timeout=2)
    server.server_close()
    return result


def test_handler_rejects_missing_auth() -> None:
    with patch.object(service, "AUTH_TOKEN", "secret"):
        status, payload = _request("/v1/status")
    assert status == 401
    assert "invalid bearer token" in payload


def test_handler_dispatches_only_allowlisted_operation() -> None:
    with patch.object(service, "AUTH_TOKEN", "secret"):
        status, payload = _request(
            "/v1/actions/not-a-command", method="POST", token="secret"
        )
    assert status == 404
    assert "unknown recovery operation" in payload


def test_handler_dispatches_authorized_operation() -> None:
    with (
        patch.object(service, "AUTH_TOKEN", "secret"),
        patch.object(service, "status", return_value={"ok": True, "source": "test"}),
    ):
        status, payload = _request("/v1/status", token="secret")
    assert status == 200
    assert '"source":"test"' in payload


def test_run_wraps_os_errors() -> None:
    with patch.object(service.subprocess, "run", side_effect=PermissionError("denied")):
        try:
            service._run(["fixed-command"])
        except service.RecoveryError as exc:
            assert "fixed-command" in str(exc)
        else:
            raise AssertionError("RecoveryError was not raised")
