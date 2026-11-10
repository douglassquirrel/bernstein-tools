import datetime

import pytest

from bernstein import podium

NOW = datetime.datetime(2026, 10, 18, 9, 40, 5, tzinfo=datetime.timezone.utc)


def row(name, state="off", kind="code", duty=None, minutes=3, pace="normal", new=0, open_=0, reported=None,
        sister="", claws=(), serves=(), refused=None):
    """A row as conduct status --json gives it. duty: None or the holder's name."""
    held = None
    if duty:
        held = {"mailbox": name, "holder": duty, "since": "2026-10-18T09:00:00Z",
                "last_beat": "2026-10-18T09:37:00Z", "stale": state in ("stale", "quiet"), "minutes": minutes}
    known = kind is not None
    return {"mailbox": name, "state": state, "kind": kind, "folder": "/p/" + name if known else None,
            "model": "opus" if known else None, "effort": "high" if known else None,
            "sister": sister if known else None, "claws": list(claws), "serves": list(serves),
            "refused": refused, "duty": held, "pace": pace, "new": new, "open": open_,
            "handover_waiting": state == "handed-over", "reported": reported}


@pytest.mark.parametrize("minutes, text", [
    (0, "just now"), (1, "1 min ago"), (3, "3 min ago"), (59, "59 min ago"), (60, "1 h ago"),
    (125, "2 h 5 min ago"), (1439, "23 h 59 min ago"), (1440, "1 d ago"), (4500, "3 d ago"),
])
def test_how_long_ago_a_session_checked_in_is_said_in_minutes_hours_or_days(minutes, text):
    assert podium.ago(minutes) == text


def test_how_long_ago_is_unknown_when_the_listing_gives_no_number():
    assert podium.ago(None) == "at an unknown time" and podium.ago("soon") == "at an unknown time"


DREAMING = {"status": "dreaming", "set": "2026-10-18T09:20:00Z", "until": "2026-10-18T10:20:00Z"}


@pytest.mark.parametrize("state, text, tone", [
    ("running", "running", "ok"), ("dormant", "dormant", "sleep"), ("quiet", "quiet", "warn"),
    ("stale", "stale", "alert"), ("handed-over", "handed over", "off"), ("off", "off", "off"),
])
def test_the_badge_names_the_state_and_its_tone(state, text, tone):
    assert podium.badge(row("recipes", state, duty="mac"), NOW) == (text, tone)


def test_a_running_session_s_reported_status_takes_the_badge_until_its_finish_time():
    assert podium.badge(row("recipes", "running", duty="mac", reported=DREAMING), NOW) == \
        ("dreaming until 10:20 UTC", "busy")
    no_end = {"status": "waiting for Squirrel", "set": "2026-10-18T09:20:00Z", "until": None}
    assert podium.badge(row("recipes", "running", duty="mac", reported=no_end), NOW) == \
        ("waiting for Squirrel", "busy")


def test_a_reported_status_past_its_finish_time_is_shown_as_overdue_not_trusted():
    late = datetime.datetime(2026, 10, 18, 11, 0, tzinfo=datetime.timezone.utc)
    assert podium.badge(row("recipes", "running", duty="mac", reported=DREAMING), late) == \
        ("dreaming, overdue since 10:20 UTC", "warn")


def test_a_finish_time_on_another_day_names_the_day_and_one_that_is_not_a_time_is_shown_as_given():
    tomorrow = dict(DREAMING, until="2026-10-19T01:00:00Z")
    assert podium.badge(row("recipes", "running", duty="mac", reported=tomorrow), NOW)[0] == \
        "dreaming until 01:00 UTC on 19 October 2026"
    odd = dict(DREAMING, until="teatime")
    assert podium.badge(row("recipes", "running", duty="mac", reported=odd), NOW) == \
        ("dreaming until teatime", "busy")


def test_a_report_does_not_take_the_badge_from_any_state_but_running():
    assert podium.badge(row("recipes", "quiet", duty="mac", reported=DREAMING), NOW) == ("quiet", "warn")
    said = {"status": "dormant", "set": "2026-10-18T09:20:00Z", "until": None}
    assert podium.badge(row("recipes", "dormant", duty="mac", reported=said), NOW) == ("dormant", "sleep")


def a_factory():
    return [
        row("bernstein", "running", kind=None, duty="mac", refused="no lobster.conf"),
        row("lone-tools", "off"),
        row("menus", "running", kind="non-code", duty="mac", sister="video-tools", claws=["video-tools"]),
        row("old-thing", "handed-over", kind=None, refused="/p/old-thing has no lobster.conf"),
        row("recipes", "running", kind="non-code", duty="mac", sister="recipes-tools",
            claws=["recipes-tools", "video-tools", "gone-tools"]),
        row("recipes-tools", "handed-over", sister="recipes", serves=["recipes"]),
        row("video-tools", "stale", duty="mac", sister="menus", serves=["menus", "recipes"]),
    ]


def test_rows_are_grouped_a_card_per_non_code_project_then_lone_claws_then_the_rest_then_bernstein():
    g = podium.groups(a_factory())
    assert [(head["mailbox"], [(c["mailbox"], label) for c, label in claws]) for head, claws in g["cards"]] == [
        ("menus", [("video-tools", "home claw")]),
        ("recipes", [("recipes-tools", "home claw"), ("video-tools", "claw"), ("gone-tools", "claw")])]
    assert [r["mailbox"] for r in g["lone"]] == ["lone-tools"]
    assert [r["mailbox"] for r in g["unstartable"]] == ["old-thing"]
    assert g["bernstein"]["mailbox"] == "bernstein"


def test_a_claw_named_by_a_project_but_with_no_mailbox_is_shown_as_such():
    g = podium.groups(a_factory())
    gone = g["cards"][1][1][2][0]
    assert gone == {"mailbox": "gone-tools", "missing": True}


def test_groups_with_nothing_in_them_are_empty_and_bernstein_may_be_absent():
    assert podium.groups([]) == {"cards": [], "lone": [], "unstartable": [], "bernstein": None}


def test_the_view_says_when_it_was_made_and_lays_out_cards_then_sections():
    html = podium.view(a_factory(), NOW)
    assert '<p class="asof">As of 09:40:05 UTC</p>' in html
    order = [html.index(mark) for mark in (
        '<span class="name">menus</span>', '<span class="name">recipes</span>', "<h2>Lone claws</h2>",
        '<span class="name">lone-tools</span>', "<h2>Cannot be started</h2>", '<span class="name">old-thing</span>',
        "<h2>bernstein</h2>", '<span class="name">bernstein</span>')]
    assert order == sorted(order)
    assert html.count('<section class="card">') == 5      # menus, recipes, lone claws, cannot be started, bernstein


def test_a_row_shows_its_kind_badge_duty_pace_mail_and_model():
    html = podium.view([row("recipes", "running", kind="non-code", duty="mac", minutes=3, pace="eager", new=2,
                            open_=1, sister="recipes-tools", claws=["recipes-tools"]),
                        row("recipes-tools", "handed-over", sister="recipes", serves=["recipes"])], NOW)
    assert ('<div class="row"><div class="who"><span class="name">recipes</span> <span class="kind">non-code</span>'
            '</div><span class="badge ok">running</span><ul class="facts"><li>mac, checked in 3 min ago</li>'
            '<li>pace eager</li><li class="new">2 new</li><li>1 open</li><li>opus, high</li></ul></div>') in html
    assert ('<div class="row claw"><div class="who"><span class="name">recipes-tools</span> '
            '<span class="kind">home claw</span></div><span class="badge off">handed over</span>'
            '<ul class="facts"><li>nobody on duty</li><li>pace normal</li><li>0 new</li><li>0 open</li>'
            '<li>opus, high</li></ul></div>') in html


def test_a_row_says_why_its_project_cannot_be_started_and_a_missing_claw_has_no_mailbox():
    html = podium.view(a_factory(), NOW)
    assert '<p class="refused">Cannot start: /p/old-thing has no lobster.conf</p>' in html
    assert ('<div class="row claw"><div class="who"><span class="name">gone-tools</span> '
            '<span class="kind">claw</span></div><span class="badge off">no mailbox</span></div>') in html


def test_a_report_that_is_not_in_the_badge_is_among_the_facts():
    quiet = podium.view([row("lone-tools", "quiet", duty="mac", pace="relaxed", reported=DREAMING)], NOW)
    assert "<li>reporting &quot;dreaming&quot;</li>" in quiet
    running = podium.view([row("lone-tools", "running", duty="mac", reported=DREAMING)], NOW)
    assert '<span class="badge busy">dreaming until 10:20 UTC</span>' in running and "reporting" not in running


def test_sections_with_nothing_in_them_are_left_out_and_no_mailboxes_is_said():
    html = podium.view([row("lone-tools", "off")], NOW)
    assert "<h2>Lone claws</h2>" in html and "Cannot be started" not in html and "<h2>bernstein</h2>" not in html
    assert '<p class="empty">No mailboxes.</p>' in podium.view([], NOW)


def test_an_error_from_conduct_is_shown_in_place_of_the_cards():
    html = podium.view([], NOW, error="conduct status failed (exit 4)\n  lobster-mail: gone")
    assert '<p class="error">conduct status failed (exit 4)\n  lobster-mail: gone</p>' in html
    assert "No mailboxes" not in html and '<p class="asof">As of 09:40:05 UTC</p>' in html


def test_everything_from_outside_is_escaped_as_text_never_markup():
    nasty = '</script><script>alert("x")</script> & \'q\' café'
    hostile = row(nasty, "running", duty=nasty, pace=nasty, refused=nasty,
                  reported={"status": nasty, "set": "x", "until": nasty})
    hostile["model"] = hostile["effort"] = nasty
    html = podium.view([hostile], NOW, error=None) + podium.view([], NOW, error=nasty)
    assert "<script" not in html and "</script" not in html and 'alert("x")' not in html
    assert html.count("&lt;/script&gt;&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &#x27;q&#x27; café") >= 6


def test_the_page_wraps_the_view_with_its_own_styles_and_a_refresh_every_15_seconds():
    html = podium.page("<p>THE VIEW</p>")
    assert html.startswith("<!doctype html>") and "<title>podium</title>" in html
    assert '<main id="view"><p>THE VIEW</p></main>' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "prefers-color-scheme: dark" in html and '<button id="refresh" type="button">Refresh</button>' in html
    assert "setInterval(refresh, 15000)" in html and 'fetch("/view?t="' in html
    assert "http://" not in html and "https://" not in html      # nothing is loaded from anywhere else


def test_bernstein_s_own_row_does_not_say_it_cannot_be_started_since_conduct_never_starts_it():
    html = podium.view(a_factory(), NOW)
    own = html[html.index("<h2>bernstein</h2>"):]
    assert '<span class="name">bernstein</span>' in own and "Cannot start" not in own
    assert html.count("Cannot start") == 1          # old-thing still says why
