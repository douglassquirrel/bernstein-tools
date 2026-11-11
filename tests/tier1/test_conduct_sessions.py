import json
import os

from bernstein import conduct

A = "local_11111111-1111-4111-8111-111111111111"
B = "local_22222222-2222-4222-8222-222222222222"
C = "local_33333333-3333-4333-8333-333333333333"
D = "local_44444444-4444-4444-8444-444444444444"


def session(store, sid, cwd, last, archived=False, account="acct/org", **more):
    """One session file as the desktop app keeps it (invented): only the fields conduct reads, and one it must not need."""
    folder = os.path.join(store, account)
    os.makedirs(folder, exist_ok=True)
    data = {"sessionId": sid, "cwd": cwd, "originCwd": cwd, "isArchived": archived, "lastActivityAt": last,
            "postTurnSummary": "private words conduct never passes on"}
    data.update(more)
    with open(os.path.join(folder, sid + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f)


def test_the_newest_session_that_is_not_archived_is_found_for_each_folder(tmp_path):
    store, tools, other = str(tmp_path / "store"), str(tmp_path / "recipes-tools"), str(tmp_path / "other")
    os.makedirs(tools)
    os.makedirs(other)
    session(store, A, tools, 1794401000000)
    session(store, B, tools, 1794401892175)                    # the newest for recipes-tools
    session(store, C, tools, 1794409999999, archived=True)     # newer still, but archived
    session(store, D, other, 1794300000000, account="acct2/org2")
    assert conduct.app_sessions(store) == {
        os.path.realpath(tools): {"id": B, "link": "claude://claude.ai/epitaxy/" + B,
                                  "last_activity": "2026-11-11T12:58:12Z"},
        os.path.realpath(other): {"id": D, "link": "claude://claude.ai/epitaxy/" + D,
                                  "last_activity": "2026-11-10T08:40:00Z"}}


def test_a_folder_reached_through_a_link_is_the_same_folder(tmp_path):
    store, real, alias = str(tmp_path / "store"), str(tmp_path / "real"), str(tmp_path / "alias")
    os.makedirs(real)
    os.symlink(real, alias)
    session(store, A, alias, 1794401892175)
    assert list(conduct.app_sessions(store)) == [os.path.realpath(real)]


def test_files_that_are_not_sessions_are_passed_over_and_a_missing_store_gives_nothing(tmp_path):
    store, tools = str(tmp_path / "store"), str(tmp_path / "recipes-tools")
    os.makedirs(tools)
    session(store, A, tools, 1794401892175)
    folder = os.path.join(store, "acct", "org")
    for name, text in (("local_not-json.json", "{"), ("archived-sessions.idx", "x"), ("scheduled-tasks.json", "[]"),
                       (B + ".json", json.dumps(["a list"])),
                       (C + ".json", json.dumps({"sessionId": C, "cwd": 7, "isArchived": False, "lastActivityAt": 9})),
                       (D + ".json", json.dumps({"sessionId": "local_other", "cwd": tools, "isArchived": False,
                                                 "lastActivityAt": 1794409999999}))):
        with open(os.path.join(folder, name), "w") as f:
            f.write(text)
    session(store, "local_55555555-5555-4555-8555-555555555555", tools, "yesterday")       # no time: passed over
    session(store, "local_66666666-6666-4666-8666-666666666666", tools, 1794409999999, archived="no")
    session(store, "evil_66666666-6666-4666-8666-666666666666", tools, 1794409999999)
    assert [s["id"] for s in conduct.app_sessions(store).values()] == [A]
    assert conduct.app_sessions(str(tmp_path / "nowhere")) == {}
    assert conduct.app_sessions(os.path.join(folder, A + ".json")) == {}       # a file, not a folder


def test_reading_the_store_changes_nothing_in_it(tmp_path):
    store, tools = str(tmp_path / "store"), str(tmp_path / "recipes-tools")
    os.makedirs(tools)
    session(store, A, tools, 1794401892175)
    path = os.path.join(store, "acct", "org", A + ".json")

    def seen():
        with open(path, "rb") as f:
            return f.read(), os.stat(path).st_mtime_ns, sorted(os.listdir(os.path.dirname(path)))

    before = seen()
    conduct.app_sessions(store)
    assert seen() == before


def test_a_row_carries_its_project_s_session_or_none():
    from types import SimpleNamespace

    def lookup(name):
        if name == "bernstein":
            raise conduct.ProjectRefused("no lobster.conf")
        return SimpleNamespace(name=name, kind="code", folder="/p/" + name, checkout="/p/" + name, sister="",
                               claws=[], claw_names=[], model="opus", effort="high")

    found = {"/p/recipes-tools": {"id": A, "link": "claude://claude.ai/epitaxy/" + A,
                                  "last_activity": "2026-11-11T12:58:12Z"},
             "/p/bernstein-code": {"id": B, "link": "claude://claude.ai/epitaxy/" + B,
                                   "last_activity": "2026-11-11T12:00:00Z"}}
    boxes = {n: {"mailbox": n, "duty": None} for n in ("bernstein", "lone-tools", "recipes-tools")}
    rows = {r["mailbox"]: r for r in conduct.status_rows(
        boxes, lookup, sessions=found, folder_of=lambda n: "/p/bernstein-code" if n == "bernstein" else None)}
    assert rows["recipes-tools"]["session"] == found["/p/recipes-tools"]
    assert rows["lone-tools"]["session"] is None
    assert rows["bernstein"]["kind"] is None and rows["bernstein"]["folder"] == "/p/bernstein-code"
    assert rows["bernstein"]["session"] == found["/p/bernstein-code"]
    plain = conduct.status_rows(boxes, lookup)
    assert all(r["session"] is None for r in plain) and plain[0]["folder"] is None
