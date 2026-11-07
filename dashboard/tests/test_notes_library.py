import datetime

import pytest

from notes_library import NoteLibrary, NoteRefused, category_of, purge_phrase

NOW = datetime.datetime(2026, 11, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def lib(tmp_path):
    return NoteLibrary(str(tmp_path), clock=lambda: NOW)


def rev(lib, name):
    return lib.entry(lib.directory / name)["revision"]


def test_create_names_dates_and_categorises(lib):
    made = lib.create("Probate Deed", "hello", category=4)
    assert made["filename"].endswith("_04-probate-deed.md") and made["category"] == 4
    assert made["category_name"] == "Probate & Real Estate"
    assert (lib.directory / made["filename"]).read_text() == "hello\n"


def test_create_never_overwrites(lib):
    a = lib.create("same", "one")
    b = lib.create("same", "two")
    assert a["filename"] != b["filename"] and b["filename"].endswith("-2.md")
    assert (lib.directory / a["filename"]).read_text() == "one\n"


@pytest.mark.parametrize("name,text,cat", [("", "x", None), ("!!!", "x", None), ("ok", "  ", None), ("ok", "x", 11)])
def test_create_refuses_bad_input(lib, name, text, cat):
    with pytest.raises(NoteRefused):
        lib.create(name, text, cat)


def test_list_and_search_cover_every_note(lib):
    lib.create("alpha", "needle in here\nsecond", category=2)
    lib.create("beta", "nothing", category=4)
    assert len(lib.list_all()) == 2
    found = lib.list_all("NEEDLE")
    assert [e["category"] for e in found] == [2] and found[0]["matches"][0]["line"] == 1
    assert [e["category"] for e in lib.list_all(category=4)] == [4]


def test_rename_and_move_keep_text_and_date(lib):
    name = lib.create("draft", "body", category=1)["filename"]
    moved = lib.rename(name, rev(lib, name), category=4)
    assert moved["filename"] == "2026-11-07_04-draft.md" and moved["renamed_from"] == name
    assert not (lib.directory / name).exists()
    renamed = lib.rename(moved["filename"], moved["revision"], new_name="Final Deed")
    assert renamed["filename"] == "2026-11-07_04-final-deed.md"
    assert (lib.directory / renamed["filename"]).read_text() == "body\n"
    plain = lib.rename(renamed["filename"], renamed["revision"], clear_category=True)
    assert plain["filename"] == "2026-11-07_final-deed.md" and plain["category"] is None


def test_rename_refuses_stale_revision_and_collisions(lib):
    a = lib.create("a", "1")["filename"]
    b = lib.create("b", "2")["filename"]
    with pytest.raises(FileExistsError):
        lib.rename(a, "0" * 64, new_name="x")
    with pytest.raises(NoteRefused):
        lib.rename(a, rev(lib, a), new_name="b")
    assert (lib.directory / b).read_text() == "2\n"


def test_trash_is_hidden_then_restores(lib):
    name = lib.create("keep", "precious")["filename"]
    gone = lib.trash(name, rev(lib, name))
    assert [e["filename"] for e in lib.list_all()] == []
    assert lib.list_trash()[0]["filename"] == name
    back = lib.restore(gone["trash_id"])
    assert back["filename"] == name and (lib.directory / name).read_text() == "precious\n"
    assert lib.list_trash() == []


def test_restore_never_overwrites_a_reused_name(lib):
    name = lib.create("dup", "old")["filename"]
    trash_id = lib.trash(name, rev(lib, name))["trash_id"]
    (lib.directory / name).write_text("new\n")
    back = lib.restore(trash_id)
    assert back["filename"] == name.replace(".md", "-restored.md")
    assert (lib.directory / name).read_text() == "new\n"


def test_trash_refuses_stale_revision(lib):
    name = lib.create("x", "1")["filename"]
    with pytest.raises(FileExistsError):
        lib.trash(name, "f" * 64)
    assert (lib.directory / name).exists()


def test_purge_only_from_trash_and_only_with_the_exact_phrase(lib):
    name = lib.create("doomed", "bye")["filename"]
    with pytest.raises(NoteRefused):
        lib.purge(name, purge_phrase(name))  # a live note is not a trash id
    trash_id = lib.trash(name, rev(lib, name))["trash_id"]
    for wrong in ("", "yes", purge_phrase("other")):
        with pytest.raises(PermissionError):
            lib.purge(trash_id, wrong)
    assert lib.list_trash()
    assert lib.purge(trash_id, purge_phrase(trash_id))["purged"] is True
    assert lib.list_trash() == []


def test_paths_cannot_escape(lib):
    for bad in ("../x.md", "a/b.md", ".trash", "x.txt", ".hidden.md"):
        with pytest.raises(NoteRefused):
            lib.trash(bad, "r")


def test_category_of():
    assert category_of("2026-11-05_04-x.md") == 4 and category_of("2026-11-05_x.md") is None
    assert category_of("2026-11-05_99-x.md") is None
