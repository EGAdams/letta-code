from notes_adw_gateway import NotesAdwGateway, VERSION, json_command


class Transport:
    def __init__(self):
        self.calls = []

    def dispatch_notes_control(self, control, args):
        self.calls.append((control, dict(args)))
        return {"status": "acknowledged", "browser_permission_required": control.startswith("record")}


def command(name, key="k1", role="chatgpt"):
    return {"version": VERSION, "command": name, "task_id": "t_4412b1b5df933e6ccdd32a10",
            "correlation_id": "c1", "role": role, "args": {"note_id": "n1"},
            "idempotency_key": key}


def test_chatgpt_and_toyota_use_the_same_control_dispatch():
    transport = Transport()
    gateway = NotesAdwGateway(transport)
    assert gateway.execute(command("notes.record.start"))["ok"]
    assert gateway.execute(command("notes.record.start", key="k2", role="toyota"))["ok"]
    assert transport.calls == [("record.start", {"note_id": "n1"}), ("record.start", {"note_id": "n1"})]


def test_duplicate_is_idempotent_and_not_dispatched_twice():
    transport = Transport()
    gateway = NotesAdwGateway(transport)
    first = gateway.execute(command("notes.save"))
    second = gateway.execute(command("notes.save"))
    assert first["result"] == second["result"]
    assert second["duplicate"] is True
    assert len(transport.calls) == 1


def test_invalid_role_and_missing_task_id_fail_closed():
    transport = Transport()
    gateway = NotesAdwGateway(transport)
    assert gateway.execute(command("notes.status", role="admin"))["ok"] is False
    request = command("notes.save")
    request["task_id"] = ""
    assert gateway.execute(request)["ok"] is False


def test_json_boundary_is_safe_and_preserves_browser_ack():
    transport = Transport()
    response = json_command(__import__("json").dumps(command("notes.record.stop")), NotesAdwGateway(transport))
    assert __import__("json").loads(response)["result"]["browser_permission_required"] is True
