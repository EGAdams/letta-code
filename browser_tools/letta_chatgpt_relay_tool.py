def relay_message_to_chatgpt(
    message: str,
    browser_server_url: str = "",
    executor_url: str = "",
    executor_token: str = "",
    timeout_seconds: int = 180,
    poll_seconds: int = 10,
    stability_checks: int = 2,
    max_total_seconds: int = 600,
) -> str:
    """
    Send a message to the controlled ChatGPT browser and return ChatGPT's reply.

    The tool uses the local browser server API documented in API_GUIDE.md:
    it posts to /type, posts to /send, then polls /read_thread until the
    latest assistant reply appears stable.

    Args:
        message: The message to relay to ChatGPT.
        browser_server_url: Optional base URL for the browser server. If empty,
            the tool tries BROWSER_SERVER_URL and common local Docker/host URLs.
        executor_url: Optional base URL for executor_server.py. If set, browser
            API calls are executed through POST /run on the executor.
        executor_token: Optional bearer token for executor_server.py.
        timeout_seconds: Seconds to wait without progress before timing out.
        poll_seconds: Seconds between /read_thread polls.
        stability_checks: Number of consecutive identical assistant reads that
            mean the assistant is done speaking.
        max_total_seconds: Absolute cap for the whole relay operation.

    Returns:
        A JSON string containing status, response, thread, and diagnostics.
    """
    import json
    import os
    import shlex
    import time
    import urllib.error
    import urllib.parse
    import urllib.request

    def normalize_base_url(raw_url: str) -> str:
        return raw_url.rstrip("/")

    def request_json(base_url: str, method: str, path: str, payload=None, timeout: int = 20):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            normalize_base_url(base_url) + path,
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
        return json.loads(raw) if raw else {}

    def executor_candidates() -> list[str]:
        candidates = [
            executor_url,
            os.environ.get("EXECUTOR_URL", ""),
            "http://100.72.158.63:8787",
            "http://10.0.0.7:8787",
            "http://100.80.49.10:8787",
        ]
        seen = set()
        urls = []
        for candidate in candidates:
            if not candidate:
                continue
            normalized = normalize_base_url(candidate)
            if normalized not in seen:
                seen.add(normalized)
                urls.append(normalized)
        return urls

    def resolve_executor() -> tuple[str, str] | None:
        token = (
            executor_token
            or os.environ.get("EXECUTOR_TOKEN", "")
            or "fd023ff5be687a9ff5486fa7321aa4a4c1dcf0040b7fc34d"
        )
        errors = []
        for candidate in executor_candidates():
            try:
                health = request_json(candidate, "GET", "/health", timeout=5)
                if health.get("ok") is True:
                    return candidate, token
                errors.append(f"{candidate}: unhealthy response {health!r}")
            except Exception as exc:
                errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
        return None

    def run_via_executor(executor: tuple[str, str], command: str, timeout: int = 30) -> str:
        base, token = executor
        payload = {"command": command, "cwd": ".", "timeout_sec": timeout}
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            normalize_base_url(base) + "/run",
            data=data,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout + 10) as response:
            result = json.loads(response.read().decode("utf-8", "replace"))
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(
                "executor curl failed: "
                + str(result.get("stderr") or result.get("stdout") or result)
            )
        return str(result.get("stdout") or "")

    def request_json_via_executor(
        executor: tuple[str, str],
        browser_base_url: str,
        method: str,
        path: str,
        payload=None,
        timeout: int = 30,
    ):
        url = normalize_base_url(browser_base_url) + path
        parts = ["curl", "-sS", "--max-time", str(max(1, timeout)), "-X", method, url]
        if payload is not None:
            parts.extend(["-H", "Content-Type: application/json", "--data-raw", json.dumps(payload)])
        command = " ".join(shlex.quote(part) for part in parts)
        raw = run_via_executor(executor, command, timeout=timeout)
        return json.loads(raw) if raw else {}

    def candidate_browser_urls() -> list[str]:
        candidates = [
            browser_server_url,
            os.environ.get("BROWSER_SERVER_URL", ""),
            "http://127.0.0.1:5001",
            "http://localhost:5001",
            "http://host.docker.internal:5001",
            "http://100.80.49.10:5001",
        ]
        seen = set()
        urls = []
        for candidate in candidates:
            if not candidate:
                continue
            normalized = normalize_base_url(candidate)
            if normalized not in seen:
                seen.add(normalized)
                urls.append(normalized)
        return urls

    def resolve_browser_server_url(executor=None) -> str:
        errors = []
        for candidate in candidate_browser_urls():
            try:
                if executor:
                    health = request_json_via_executor(
                        executor,
                        candidate,
                        "GET",
                        "/health",
                        timeout=5,
                    )
                else:
                    health = request_json(candidate, "GET", "/health", timeout=5)
                if health.get("status") == "ok":
                    return candidate
                errors.append(f"{candidate}: unhealthy response {health!r}")
            except Exception as exc:
                errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
        raise RuntimeError("No reachable browser server. Tried: " + " | ".join(errors))

    def latest_assistant_text(thread: list[dict]) -> str:
        for turn in reversed(thread):
            if turn.get("role") == "assistant" and turn.get("text"):
                return str(turn["text"]).strip()
        return ""

    def latest_assistant_turn(thread: list[dict]):
        for turn in reversed(thread):
            if turn.get("role") == "assistant" and turn.get("text"):
                return turn
        return None

    def latest_user_turn(thread: list[dict]):
        for turn in reversed(thread):
            if turn.get("role") == "user" and turn.get("text"):
                return turn
        return None

    def looks_like_placeholder(text: str) -> bool:
        normalized = " ".join(text.strip().lower().split())
        return normalized in {
            "",
            "thinking",
            "thinking...",
            "working",
            "working...",
            "generating",
            "generating...",
        }

    started_at = time.time()
    executor = resolve_executor()
    try:
        base_url = resolve_browser_server_url(executor)
    except Exception as exc:
        return json.dumps(
            {
                "status": "BROWSER_SERVER_UNREACHABLE",
                "transport": "executor" if executor else "direct",
                "elapsed_seconds": round(time.time() - started_at, 1),
                "response": None,
                "thread": [],
                "turn_count": 0,
                "message": str(exc),
            },
            ensure_ascii=True,
        )

    def browser_request(method: str, path: str, payload=None, timeout: int = 30):
        if executor:
            return request_json_via_executor(executor, base_url, method, path, payload, timeout)
        return request_json(base_url, method, path, payload, timeout)

    before = browser_request("GET", "/read_thread?last=20", timeout=20)
    before_thread = before.get("thread") or []
    before_assistant = latest_assistant_turn(before_thread)
    before_assistant_id = before_assistant.get("turn_id") if before_assistant else None
    before_assistant_text = str(before_assistant.get("text", "")).strip() if before_assistant else ""
    before_user = latest_user_turn(before_thread)
    before_user_id = before_user.get("turn_id") if before_user else None

    browser_request("POST", "/type", {"text": message}, timeout=30)
    browser_request("POST", "/send", timeout=30)

    deadline = time.time() + max(1, timeout_seconds)
    absolute_deadline = time.time() + max(max_total_seconds, timeout_seconds)
    last_text = ""
    stable_count = 0
    last_thread = []

    while time.time() < absolute_deadline:
        thread_payload = browser_request("GET", "/read_thread?last=20", timeout=30)
        last_thread = thread_payload.get("thread") or []
        turn_count = int(thread_payload.get("turn_count") or len(last_thread))
        current_assistant = latest_assistant_turn(last_thread)
        current_assistant_id = current_assistant.get("turn_id") if current_assistant else None
        current_text = str(current_assistant.get("text", "")).strip() if current_assistant else ""
        current_user = latest_user_turn(last_thread)
        current_user_id = current_user.get("turn_id") if current_user else None

        if (
            current_user_id
            and current_user_id != before_user_id
            and current_assistant_id
            and (current_assistant_id != before_assistant_id or current_text != before_assistant_text)
            and current_text
            and not looks_like_placeholder(current_text)
        ):
            if current_text == last_text:
                stable_count += 1
            else:
                last_text = current_text
                stable_count = 1
                deadline = time.time() + max(1, timeout_seconds)

            if stable_count >= max(1, stability_checks):
                return json.dumps(
                    {
                        "status": "ok",
                        "transport": "executor" if executor else "direct",
                        "browser_server_url": base_url,
                        "elapsed_seconds": round(time.time() - started_at, 1),
                        "response": current_text,
                        "thread": last_thread,
                        "turn_count": turn_count,
                    },
                    ensure_ascii=True,
                )

        if time.time() >= deadline:
            return json.dumps(
                {
                    "status": "TIMEOUT_ERROR",
                    "transport": "executor" if executor else "direct",
                    "browser_server_url": base_url,
                    "elapsed_seconds": round(time.time() - started_at, 1),
                    "response": last_text or None,
                    "thread": last_thread,
                    "turn_count": len(last_thread),
                    "message": "Timed out waiting for a stable ChatGPT assistant reply.",
                },
                ensure_ascii=True,
            )

        time.sleep(max(1, poll_seconds))

    return json.dumps(
        {
            "status": "TIMEOUT_ERROR",
            "transport": "executor" if executor else "direct",
            "browser_server_url": base_url,
            "elapsed_seconds": round(time.time() - started_at, 1),
            "response": last_text or None,
            "thread": last_thread,
            "turn_count": len(last_thread),
            "message": "Reached absolute max_total_seconds while waiting for ChatGPT.",
        },
        ensure_ascii=True,
    )
