"""PDF attachments: the store, the Bridge routes, and the browser routes' helpers. Synthetic PDFs only."""
import base64
import hashlib
import json

import pytest

import notes_attachments
from notes_attachments import AttachmentRefused, AttachmentStore
from notes_bridge import dispatch

DEED = "2026-11-03_deed.md"
PDF = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\ntrailer << >>\n%%EOF\n"
OTHER = b"%PDF-1.7\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n%%EOF"
PREFIX = "/api/notes-bridge/v1"


@pytest.fixture
def notes(tmp_path):
    (tmp_path / DEED).write_text("deed text\n{{highlight:yellow}}[VERIFY X]{{/highlight}}\n")
    (tmp_path / "other.md").write_text("other\n")
    return tmp_path


def test_attach_stores_the_bytes_under_a_stable_id_and_leaves_the_note_alone(notes):
    before = (notes / DEED).read_bytes()
    store = AttachmentStore(str(notes))
    entry, created = store.attach(DEED, PDF, title="Latest Printable Deed PDF", name="deed.pdf")
    assert created and entry["id"] == notes_attachments.attachment_id(DEED, hashlib.sha256(PDF).hexdigest())
    assert entry["bytes"] == len(PDF) and entry["pages"] == 1 and entry["title"] == "Latest Printable Deed PDF"
    assert (notes / ".attachments" / f"{entry['id']}.pdf").read_bytes() == PDF
    assert (notes / DEED).read_bytes() == before
    again, created_again = store.attach(DEED, PDF, title="ignored")
    assert not created_again and again["id"] == entry["id"] and again["title"] == entry["title"]
    assert [a["id"] for a in store.list(DEED)] == [entry["id"]] and store.list("other.md") == []


def test_the_same_pdf_on_another_note_is_another_attachment(notes):
    store = AttachmentStore(str(notes))
    a, _ = store.attach(DEED, PDF)
    b, _ = store.attach("other.md", PDF)
    assert a["id"] != b["id"]
    with pytest.raises(AttachmentRefused, match="has no attachment"):
        store.get("other.md", a["id"])


@pytest.mark.parametrize("data,code", [
    (b"", "empty"), (b"<html>%%EOF", "not_a_pdf"), (b"%PDF-1.4\nno end", "not_a_pdf"),
    (b"%PDF-" + b"x" * (notes_attachments.MAX_BYTES) + b"%%EOF", "too_large")])
def test_what_is_not_a_whole_pdf_within_the_limit_is_refused(notes, data, code):
    with pytest.raises(AttachmentRefused) as caught:
        AttachmentStore(str(notes)).attach(DEED, data)
    assert caught.value.code == code and not (notes / ".attachments" / "index.json").exists()


def test_a_wrong_declared_hash_or_a_bad_name_or_a_missing_note_is_refused(notes):
    store = AttachmentStore(str(notes))
    with pytest.raises(AttachmentRefused, match="not the declared"):
        store.attach(DEED, PDF, declared_sha256="0" * 64)
    for bad in ("../etc/passwd.md", ".attachments", "a/b.md", ""):
        with pytest.raises(AttachmentRefused):
            store.attach(bad, PDF)
    with pytest.raises(FileNotFoundError):
        store.attach("2099-01-01_absent.md", PDF)
    with pytest.raises(AttachmentRefused, match="12 hex"):
        store.get(DEED, "../../index")


def test_inspect_recomputes_the_hash_from_disk_and_notices_damage(notes):
    store = AttachmentStore(str(notes))
    entry, _ = store.attach(DEED, PDF)
    assert store.get(DEED, entry["id"])["intact"]
    (notes / ".attachments" / f"{entry['id']}.pdf").write_bytes(OTHER)
    assert not store.get(DEED, entry["id"])["intact"]
    with pytest.raises(AttachmentRefused, match="no longer matches"):
        store.content(DEED, entry["id"])
    restored, created = store.attach(DEED, PDF)                    # attaching again repairs it
    assert created and store.content(DEED, entry["id"])[1] == PDF


def test_remove_is_soft_and_attaching_again_brings_it_back(notes):
    store = AttachmentStore(str(notes))
    entry, _ = store.attach(DEED, PDF)
    store.remove(DEED, entry["id"])
    assert store.list(DEED) == [] and list((notes / ".attachments" / ".removed").iterdir())
    with pytest.raises(AttachmentRefused):
        store.remove(DEED, entry["id"])
    back, created = store.attach(DEED, PDF)
    assert created and back["id"] == entry["id"] and store.list(DEED)[0]["id"] == entry["id"]


def test_a_file_name_is_made_safe(notes):
    assert notes_attachments.safe_name("../../x/Deed REVISED.pdf", "a-1") == "Deed REVISED.pdf"
    assert notes_attachments.safe_name("<script>", "a-1") == "_script_.pdf"
    assert notes_attachments.safe_name("", "a-1") == "a-1.pdf"


# ---- the Bridge routes -------------------------------------------------------------------------------------

class Repo:
    def __init__(self, directory):
        self.directory = str(directory)


class Auth:
    def __init__(self):
        self.scopes = []

    def authorize(self, client_ip, headers, scope):
        self.scopes.append(scope)
        return "agent-bridge-notes"


@pytest.fixture
def bridge(notes, tmp_path_factory, monkeypatch):
    import notes_bridge
    conf = tmp_path_factory.mktemp("conf")
    log = conf / "activity.jsonl"
    monkeypatch.setenv("NOTES_ACTIVITY_LOG", str(log))
    (conf / "approved.json").write_text(json.dumps({"all": True}))
    monkeypatch.setenv("NOTES_BRIDGE_APPROVED", str(conf / "approved.json"))
    monkeypatch.setenv("NOTES_BRIDGE_PROTECTED", str(conf / "protected.json"))
    auth = Auth()
    monkeypatch.setattr(notes_bridge.composition, "authorizer", lambda: auth)
    monkeypatch.setattr(notes_bridge.note_repository, "build_note_repository", lambda: Repo(notes))

    def call(method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        status, raw = dispatch(method, PREFIX + path, {"x-bridge-task": "t_0123456789abcdef"}, "127.0.0.1", body)
        return status, json.loads(raw)
    call.auth, call.conf = auth, conf
    call.events = lambda: [json.loads(x) for x in log.read_text().splitlines()]
    return call


def attach_body(data=PDF, **extra):
    return {"pdf_base64": base64.b64encode(data).decode(), "title": "Latest Printable Deed PDF",
            "name": "Personal_Representative_Deed_for_Notary_REVISED.pdf", **extra}


def test_bridge_attach_list_inspect_and_remove(bridge, notes):
    before = (notes / DEED).read_bytes()
    status, out = bridge("POST", f"/notes/{DEED}/attachments",
                         attach_body(sha256=hashlib.sha256(PDF).hexdigest()))
    assert status == 201 and out["created"] and bridge.auth.scopes[-1] == "notes:write"
    ident = out["attachment"]["id"]
    assert out["attachment"]["filename"] == "Personal_Representative_Deed_for_Notary_REVISED.pdf"
    status, out = bridge("POST", f"/notes/{DEED}/attachments", attach_body())
    assert status == 200 and not out["created"]
    status, out = bridge("GET", f"/notes/{DEED}/attachments")
    assert status == 200 and [a["id"] for a in out["attachments"]] == [ident]
    status, out = bridge("GET", f"/notes/{DEED}/attachments/{ident}?content=1")
    assert status == 200 and out["attachment"]["intact"] and base64.b64decode(out["pdf_base64"]) == PDF
    status, out = bridge("GET", f"/notes/{DEED}/attachments/{ident}")
    assert "pdf_base64" not in out and bridge.auth.scopes[-1] == "notes:read"
    status, out = bridge("POST", f"/notes/{DEED}/attachments/{ident}/remove", {})
    assert status == 200 and out["removed"]
    assert bridge("GET", f"/notes/{DEED}/attachments")[1]["attachments"] == []
    assert (notes / DEED).read_bytes() == before
    events = [e["event"] for e in bridge.events()]
    assert events == ["attach_pdf", "attach_pdf", "attachments", "attachment", "attachment", "detach_pdf",
                      "attachments"]
    assert all(e["task_id"] == "t_0123456789abcdef" and e["actor"] == "agent-bridge-notes" for e in bridge.events())


def test_bridge_refusals_are_logged_and_change_nothing(bridge, notes):
    assert bridge("POST", f"/notes/{DEED}/attachments", attach_body(b"GIF89a"))[1]["error"] == "not_a_pdf"
    assert bridge("POST", f"/notes/{DEED}/attachments", {"pdf_base64": "@@@"})[1]["error"] == "bad_base64"
    assert bridge("POST", f"/notes/{DEED}/attachments", {})[1]["error"] == "pdf_base64_required"
    assert bridge("GET", f"/notes/{DEED}/attachments/a-000000000000")[0] == 404
    assert bridge("GET", f"/notes/{DEED}/attachments/nope")[1]["error"] == "bad_attachment_id"
    assert bridge("POST", "/notes/2099-01-01_absent.md/attachments", attach_body())[0] == 404
    assert bridge("DELETE", f"/notes/{DEED}/attachments")[0] == 405
    assert bridge("GET", f"/notes/{DEED}/attachments/a-000000000000/remove")[0] == 405
    assert not (notes / ".attachments" / "index.json").exists()
    assert "attachment_refused" in [e["event"] for e in bridge.events()]


def test_a_protected_note_can_be_read_but_takes_no_attachment(bridge, notes):
    (bridge.conf / "protected.json").write_text(json.dumps({"notes": [DEED]}))
    status, out = bridge("POST", f"/notes/{DEED}/attachments", attach_body())
    assert status == 403 and out["error"] == "note_protected"
    assert bridge("GET", f"/notes/{DEED}/attachments")[0] == 200


# ---- the browser routes ------------------------------------------------------------------------------------

def test_browser_routes_list_and_send_the_pdf_inline_or_as_a_download(notes):
    entry, _ = AttachmentStore(str(notes)).attach(DEED, PDF, name="Deed REVISED.pdf")
    seen = []
    record = lambda event, **f: seen.append((event, f["detail"]))
    status, body, ctype, _ = notes_attachments.serve(str(notes), notes_attachments.BROWSER_LIST, {"filename": [DEED]}, record)
    assert status == 200 and json.loads(body)["attachments"][0]["id"] == entry["id"]
    query = {"filename": [DEED], "id": [entry["id"]]}
    status, body, ctype, headers = notes_attachments.serve(str(notes), notes_attachments.BROWSER_FILE, query, record)
    assert status == 200 and body == PDF and ctype == "application/pdf"
    assert dict(headers)["Content-Disposition"] == 'inline; filename="Deed REVISED.pdf"'
    _, _, _, headers = notes_attachments.serve(str(notes), notes_attachments.BROWSER_FILE, {**query, "download": ["1"]}, record)
    assert dict(headers)["Content-Disposition"].startswith("attachment;")
    assert [e for e, _ in seen] == ["attachment_view", "attachment_download"]


def test_browser_routes_refuse_a_bad_id_a_missing_note_and_a_damaged_file(notes):
    entry, _ = AttachmentStore(str(notes)).attach(DEED, PDF)
    serve = lambda q: notes_attachments.serve(str(notes), notes_attachments.BROWSER_FILE, q, lambda *a, **k: None)[0]
    assert serve({"filename": [DEED], "id": ["../index.json"]}) == 400
    assert serve({"filename": ["2099-01-01_absent.md"], "id": [entry["id"]]}) == 404
    assert serve({"filename": [DEED], "id": ["a-000000000000"]}) == 404
    (notes / ".attachments" / f"{entry['id']}.pdf").write_bytes(OTHER)
    assert serve({"filename": [DEED], "id": [entry["id"]]}) == 500
