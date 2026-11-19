import datetime
from types import SimpleNamespace

import pytest

from bernstein import conduct

NOW = datetime.datetime(2026, 10, 18, 9, 40, tzinfo=datetime.timezone.utc)


def box(duty=None, pace="normal", handover=False, reported=None, name="recipes", new=0, open_=0):
    """A mailbox as lobster-mail's duty status --all --json lists it. duty: None, "fresh" or "stale"."""
    held = None
    if duty:
        held = {"mailbox": name, "holder": "mac", "since": "2026-10-18T09:00:00Z",
                "last_beat": "2026-10-18T09:30:00Z", "stale": duty == "stale", "minutes": 10,
                "reported": reported}
    return {"mailbox": name, "duty": held, "duty_changing": False, "new": new, "open": open_,
            "handover_waiting": handover, "pace": pace, "reported": reported}


DORMANT = {"status": "dormant", "set": "2026-10-18T09:20:00Z", "until": None}
DREAMING = {"status": "dreaming", "set": "2026-10-18T09:20:00Z", "until": "2026-10-18T10:20:00Z"}


@pytest.mark.parametrize("entry, state", [
    (box("fresh"), "running"),
    (box("fresh", pace="eager"), "running"),
    (box("fresh", pace="relaxed"), "running"),          # relaxed but checking in: working (Settled 95)
    (box("fresh", reported=DREAMING), "running"),       # any other report leaves the state alone
    (box("fresh", pace="relaxed", reported=DORMANT), "dormant"),   # the first 45 minutes of dormancy
    (box("stale", pace="relaxed", reported=DORMANT), "dormant"),
    (box("stale", pace="normal", reported=DORMANT), "dormant"),    # the session said so: believed at any pace
    (box("stale", pace="relaxed"), "quiet"),            # relaxed, no check-in, and it has not said dormant
    (box("stale", pace="relaxed", reported=DREAMING), "quiet"),
    (box("stale"), "stale"),
    (box("stale", pace="eager"), "stale"),
    (box(None, handover=True), "handed-over"),
    (box(None), "off"),
    (box(None, pace="relaxed"), "off"),
])
def test_the_state_follows_the_table_first_match_wins(entry, state):
    assert conduct.state_of(entry) == state


def test_a_dormant_report_counts_whatever_its_capitals_or_spaces():
    said = {"status": " Dormant ", "set": "2026-10-18T09:20:00Z", "until": None}
    assert conduct.state_of(box("stale", reported=said)) == "dormant"


def test_a_listing_from_an_older_lobster_mail_with_no_reported_or_pace_still_gets_a_state():
    old = {"mailbox": "recipes", "duty": {"holder": "mac", "stale": False}, "new": 0, "open": 0,
           "handover_waiting": False}
    assert conduct.state_of(old) == "running"
    assert conduct.state_of({"mailbox": "recipes", "duty": None}) == "off"


def project(name, kind, sister="", claws=()):
    return SimpleNamespace(name=name, kind=kind, folder="/p/" + name, checkout="/p/" + name, sister=sister,
                           claws=[], claw_names=list(claws), model="opus", effort="high")


def lookup_in(projects):
    def lookup(name):
        if name not in projects:
            raise conduct.ProjectRefused(f"no project {name} anywhere")
        return projects[name]
    return lookup


def rows_for(boxes, projects):
    return {r["mailbox"]: r for r in conduct.status_rows({b["mailbox"]: b for b in boxes}, lookup_in(projects))}


def test_a_row_joins_the_mailbox_with_what_the_project_says():
    entry = box("fresh", pace="eager", reported=DREAMING, name="recipes", new=2, open_=1)
    rows = conduct.status_rows({"recipes": entry}, lookup_in({
        "recipes": project("recipes", "non-code", "recipes-tools", ["recipes-tools", "video-tools"])}))
    assert rows == [{
        "mailbox": "recipes", "state": "running", "kind": "non-code", "folder": "/p/recipes",
        "model": "opus", "effort": "high", "sister": "recipes-tools",
        "claws": ["recipes-tools", "video-tools"], "serves": [], "refused": None,
        "duty": entry["duty"], "pace": "eager", "new": 2, "open": 1, "handover_waiting": False,
        "reported": DREAMING, "session": None, "context": None, "live": None, "live_note": None,
        "runs_in": "cowork"}]


def test_a_claw_says_which_projects_it_serves_as_sister_or_further_claw():
    rows = rows_for(
        [box(name="recipes"), box(name="menus"), box(name="recipes-tools"), box(name="video-tools"),
         box(name="lone-tools")],
        {"recipes": project("recipes", "non-code", "recipes-tools", ["recipes-tools", "video-tools"]),
         "menus": project("menus", "non-code", "video-tools", ["video-tools"]),
         "recipes-tools": project("recipes-tools", "code", "recipes"),
         "video-tools": project("video-tools", "code", "menus"),
         "lone-tools": project("lone-tools", "code", "")})
    assert rows["recipes-tools"]["serves"] == ["recipes"]
    assert rows["video-tools"]["serves"] == ["recipes", "menus"]
    assert rows["lone-tools"]["serves"] == [] and rows["lone-tools"]["sister"] == ""
    assert rows["recipes"]["serves"] == [] and rows["recipes-tools"]["claws"] == []


def test_a_mailbox_whose_project_start_would_refuse_carries_the_reason_and_no_kind():
    rows = rows_for([box("fresh", name="bernstein", open_=1)], {})
    assert rows["bernstein"] == {
        "mailbox": "bernstein", "state": "running", "kind": None, "folder": None, "model": None,
        "effort": None, "sister": None, "claws": [], "serves": [],
        "refused": "no project bernstein anywhere",
        "duty": box("fresh", name="bernstein")["duty"], "pace": "normal", "new": 0, "open": 1,
        "handover_waiting": False, "reported": None, "session": None, "context": None, "live": None,
        "live_note": None, "runs_in": None}


def test_rows_keep_the_listing_s_order_and_fill_what_an_older_lobster_mail_leaves_out():
    rows = conduct.status_rows({"zebra": {"mailbox": "zebra", "duty": None},
                                "apple": {"mailbox": "apple", "duty": None, "handover_waiting": True}},
                               lookup_in({}))
    assert [r["mailbox"] for r in rows] == ["zebra", "apple"]
    assert (rows[0]["pace"], rows[0]["new"], rows[0]["open"], rows[0]["handover_waiting"],
            rows[0]["reported"]) == ("normal", 0, 0, False, None)
    assert rows[1]["state"] == "handed-over"


def test_find_project_names_the_claws_a_non_code_project_works_with(tmp_path):
    for rel, kind, sister in (("code/recipes-tools", "code", "recipes"), ("code/video-tools", "code", "")):
        folder = tmp_path / rel
        folder.mkdir(parents=True)
        (folder / "lobster.conf").write_text(f"KIND={kind}\nSISTER={sister}\nMODEL=opus\nEFFORT=high\n")
        (folder / "START-HERE.txt").write_text("Start.\n")
    nc = tmp_path / "non-code" / "recipes"
    nc.mkdir(parents=True)
    (nc / "lobster.conf").write_text("KIND=non-code\nSISTER=recipes-tools\nCLAWS=video-tools\nMODEL=opus\nEFFORT=high\n")
    (nc / "START-HERE.txt").write_text("Start.\n")
    bases = str(tmp_path / "non-code"), str(tmp_path / "code")
    assert conduct.find_project("recipes", *bases).claw_names == ["recipes-tools", "video-tools"]
    assert conduct.find_project("recipes-tools", *bases).claw_names == []


def text_for(boxes, projects, now=NOW):
    return conduct.status_text(conduct.status_rows({b["mailbox"]: b for b in boxes}, lookup_in(projects)), now)


def test_the_text_form_is_one_aligned_line_per_mailbox():
    text = text_for(
        [box("fresh", name="recipes", new=2, open_=1, pace="eager"), box(None, name="recipes-tools", handover=True),
         box("stale", name="bernstein", pace="relaxed")],
        {"recipes": project("recipes", "non-code", "recipes-tools", ["recipes-tools"]),
         "recipes-tools": project("recipes-tools", "code", "recipes")})
    assert text == (
        "recipes        running      non-code  on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
        "  new 2  open 1  pace eager\n"
        "recipes-tools  handed-over  code      nobody on duty  new 0  open 0  pace normal\n"
        "bernstein      quiet        -         on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
        "  new 0  open 0  pace relaxed  cannot start: no project bernstein anywhere\n")


def test_the_text_form_shows_a_reported_status_and_its_finish_time():
    text = text_for([box("fresh", name="recipes", reported=DREAMING)], {"recipes": project("recipes", "non-code")})
    assert text.endswith('  pace normal  reporting "dreaming" until 2026-10-18T10:20:00Z\n')
    text = text_for([box("stale", name="recipes", pace="relaxed", reported=DORMANT)],
                    {"recipes": project("recipes", "non-code")})
    assert text.startswith("recipes  dormant  non-code  ") and text.endswith('  pace relaxed  reporting "dormant"\n')


def test_a_reported_status_past_its_finish_time_is_marked_overdue_not_trusted():
    late = NOW + datetime.timedelta(hours=1)
    text = text_for([box("fresh", name="recipes", reported=DREAMING)], {"recipes": project("recipes", "non-code")}, late)
    assert text.endswith('  reporting "dreaming" until 2026-10-18T10:20:00Z (overdue)\n')
    exactly = datetime.datetime(2026, 10, 18, 10, 20, tzinfo=datetime.timezone.utc)
    text = text_for([box("fresh", name="recipes", reported=DREAMING)], {"recipes": project("recipes", "non-code")}, exactly)
    assert text.endswith('until 2026-10-18T10:20:00Z\n')


def test_a_finish_time_that_is_not_a_time_is_shown_as_given_and_never_called_overdue():
    odd = {"status": "dreaming", "set": "2026-10-18T09:20:00Z", "until": "teatime"}
    text = text_for([box("fresh", name="recipes", reported=odd)], {"recipes": project("recipes", "non-code")})
    assert text.endswith('  reporting "dreaming" until teatime\n')


def test_an_awkward_reported_status_stays_on_its_one_line_as_data():
    nasty = {"status": 'he said "hi" \\ $HOME\n</script> café', "set": "2026-10-18T09:20:00Z", "until": None}
    text = text_for([box("fresh", name="recipes", reported=nasty)], {"recipes": project("recipes", "non-code")})
    assert text.count("\n") == 1
    assert text.endswith('  reporting "he said \\"hi\\" \\\\ $HOME\\n</script> café"\n')


def test_no_mailboxes_gives_no_lines():
    assert conduct.status_text([], NOW) == ""


def test_a_row_s_context_is_what_is_said_of_its_session_and_a_row_with_no_session_is_never_asked_about():
    code = {"id": "local_x", "app": "code"}
    cowork = {"id": "session_x", "app": "cowork"}
    asked = []

    def context(session):
        asked.append(session)
        return {"tokens": 7} if session is code else None

    boxes = {name: box(name=name) for name in ("recipes", "recipes-tools", "video-tools")}
    projects = {"recipes": project("recipes", "non-code", "recipes-tools", ("video-tools",)),
                "recipes-tools": project("recipes-tools", "code", "recipes"),
                "video-tools": project("video-tools", "code")}
    rows = {r["mailbox"]: r for r in conduct.status_rows(
        boxes, lookup_in(projects), sessions={"/p/recipes-tools": code}, cowork={"/p/recipes": cowork},
        context=context)}
    assert rows["recipes-tools"]["context"] == {"tokens": 7}
    assert rows["recipes"]["session"] == cowork and rows["recipes"]["context"] is None
    assert rows["video-tools"]["session"] is None and rows["video-tools"]["context"] is None
    assert asked == [cowork, code]


ALIVE = {"name": "recipes-tools · 18 October", "status": "idle", "kind": "interactive", "pid": 4242,
         "started": "2026-10-15T08:00:00Z", "id": "00000000-0000-4000-8000-000000000000"}


def test_a_row_of_a_project_on_the_mac_says_what_is_alive_in_its_folder_and_a_cowork_one_nothing():
    boxes = {"recipes": box("stale", name="recipes"), "recipes-tools": box("stale", name="recipes-tools")}
    projects = {"recipes": project("recipes", "non-code", "recipes-tools"),
                "recipes-tools": project("recipes-tools", "code", "recipes")}
    alive = {"/p/recipes": [ALIVE], "/p/recipes-tools": [ALIVE]}
    looked = {}
    cowork, tools = conduct.status_rows(boxes, lookup_in(projects), alive=alive, looked=looked)
    assert (cowork["live"], cowork["live_note"]) == (None, None)
    assert tools["live"] == {"name": "recipes-tools · 18 October", "status": "idle", "kind": "interactive",
                             "started": "2026-10-15T08:00:00Z", "pid": 4242, "count": 1,
                             "id": "00000000-0000-4000-8000-000000000000", "model": None, "effort": None,
                             "last_reply": None}
    told = {"model": "invented-model", "effort": "max", "last_reply": "2026-10-18T09:12:00Z"}
    (_cowork, again) = conduct.status_rows(boxes, lookup_in(projects), alive=alive, reply=lambda ident: dict(
        told, model=told["model"] + " of " + ident))
    assert {k: again["live"][k] for k in told} == dict(
        told, model="invented-model of 00000000-0000-4000-8000-000000000000")
    assert tools["live_note"] == "alive, not watching mail"
    assert looked == {"recipes-tools": [ALIVE]}
    assert conduct.status_rows(boxes, lookup_in(projects), alive=alive) == [cowork, tools]   # with nowhere to note them


def test_with_the_listing_unread_no_row_says_anything_of_a_live_session():
    looked = {}
    (row,) = conduct.status_rows({"recipes-tools": box("stale", name="recipes-tools")},
                                 lookup_in({"recipes-tools": project("recipes-tools", "code", "recipes")}),
                                 alive=None, looked=looked)
    assert (row["live"], row["live_note"], looked) == (None, None, {})
    assert "alive" not in conduct.status_text([row], NOW, looked)
