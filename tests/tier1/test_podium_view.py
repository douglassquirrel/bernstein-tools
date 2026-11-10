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
            '</div><span class="badge ok">running</span><ul class="facts"><li>mac, 3 min ago</li>'
            '<li>pace eager</li><li class="new">2 new</li><li>1 open</li><li>opus, high</li></ul>'
            '<div class="acts"><button type="button" class="act" data-verb="stop" data-project="recipes">Stop</button>'
            '<button type="button" class="act" data-verb="dormant" data-project="recipes">Dormant</button>'
            '<button type="button" class="act" data-verb="dream" data-project="recipes">Dream</button></div></div>'
            ) in html
    assert ('<div class="row claw"><div class="who"><span class="name">recipes-tools</span> '
            '<span class="kind">home claw</span></div><span class="badge off">handed over</span>'
            '<ul class="facts"><li>opus, high</li></ul><div class="acts"><button type="button" class="act" data-verb="start" '
            'data-project="recipes-tools">Start</button></div></div>') in html


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
    assert "if (!dialog.open) { refresh(); } }, 15000);" in html and 'fetch("/view?t="' in html
    assert "http://" not in html and "https://" not in html      # nothing is loaded from anywhere else


def test_bernstein_s_own_row_does_not_say_it_cannot_be_started_since_conduct_never_starts_it():
    html = podium.view(a_factory(), NOW)
    own = html[html.index("<h2>bernstein</h2>"):]
    assert '<span class="name">bernstein</span>' in own and "Cannot start" not in own
    assert html.count("Cannot start") == 1          # old-thing still says why


@pytest.mark.parametrize("state, verbs", [
    ("off", ["start"]), ("handed-over", ["start"]), ("running", ["stop", "dormant", "dream"]),
    ("dormant", ["wake"]), ("quiet", ["wake"]), ("stale", ["wake"]),
])
def test_the_buttons_a_row_offers_follow_its_state(state, verbs):
    assert podium.buttons(row("recipes-tools", state, duty="mac")) == verbs


def test_no_start_for_a_project_conduct_would_refuse_and_no_buttons_at_all_for_bernstein_or_a_missing_claw():
    assert podium.buttons(row("old-thing", "off", kind=None, refused="no lobster.conf")) == []
    assert podium.buttons(row("old-thing", "running", kind=None, duty="mac", refused="no lobster.conf")) == \
        ["stop", "dormant", "dream"]                # a session that is running can still be asked to stop
    assert podium.buttons(row("recipes-tools", "off", refused="no START-HERE.txt")) == []
    assert podium.buttons(row("bernstein", "running", kind=None, duty="mac")) == []
    assert podium.buttons({"mailbox": "gone-tools", "missing": True}) == []


def test_the_buttons_for_everything_at_once_follow_what_any_session_but_bernstein_s_is_doing():
    assert podium.buttons_for_all([row("bernstein", "running", kind=None, duty="mac"), row("a-tools", "off")]) == []
    assert podium.buttons_for_all([row("a-tools", "running", duty="mac"), row("b-tools", "off")]) == \
        ["stop", "dormant", "dream"]
    assert podium.buttons_for_all([row("a-tools", "quiet", duty="mac")]) == ["wake"]
    assert podium.buttons_for_all([row("a-tools", "running", duty="mac"), row("b-tools", "dormant", duty="mac")]) == \
        ["stop", "dormant", "dream", "wake"]
    assert podium.buttons_for_all([]) == []


def test_the_view_has_a_bar_of_buttons_for_everything_at_once_only_when_one_applies():
    html = podium.view(a_factory(), NOW)        # menus and recipes are running, video-tools is stale
    assert ('<div class="all"><button type="button" class="act" data-verb="stop" data-all="1">Stop all</button>'
            '<button type="button" class="act" data-verb="dormant" data-all="1">Dormant all</button>'
            '<button type="button" class="act" data-verb="dream" data-all="1">Dream all</button>'
            '<button type="button" class="act" data-verb="wake" data-all="1">Wake all</button></div>') in html
    assert html.index('<div class="all">') < html.index('<section class="card">')
    assert '<div class="all">' not in podium.view([row("lone-tools", "off")], NOW)


def test_a_button_s_project_name_is_escaped_as_an_attribute():
    html = podium.view([row('x" onclick="alert(1)', "off")], NOW)
    assert 'data-project="x&quot; onclick=&quot;alert(1)"' in html and 'onclick="alert' not in html


RUNS = [
    {"time": "2026-10-18T09:38:00Z", "command": "conduct stop recipes", "exit": 0,
     "output": "Sent the Stop message to recipes.\n", "error": "", "reminder": None, "log_error": None},
    {"time": "2026-10-18T09:39:30Z", "command": "conduct start menus", "exit": 3, "output": "",
     "error": "conduct: a session is already running for menus\n", "reminder": None,
     "log_error": "the log /x/podium.log could not be written (Permission denied)"},
]


def test_the_view_lists_what_podium_has_run_newest_first_with_exit_code_and_output():
    html = podium.view(a_factory(), NOW, entries=RUNS)
    assert html.index("<h2>Activity</h2>") > html.index("<h2>bernstein</h2>")
    assert html.index("conduct start menus") < html.index("conduct stop recipes")
    assert ('<div class="run"><p class="what"><span class="time">09:38:00 UTC</span> <code>conduct stop recipes</code> '
            '<span class="badge ok">exit 0</span></p><pre>Sent the Stop message to recipes.\n</pre></div>') in html
    assert ('<span class="time">09:39:30 UTC</span> <code>conduct start menus</code> <span class="badge alert">exit 3'
            '</span></p><pre>conduct: a session is already running for menus\n</pre>'
            '<p class="refused">the log /x/podium.log could not be written (Permission denied)</p></div>') in html
    assert "Activity" not in podium.view(a_factory(), NOW) and "Activity" not in podium.view(a_factory(), NOW, entries=[])


def test_activity_is_shown_even_when_conduct_status_fails_and_its_text_is_escaped():
    nasty = dict(RUNS[0], command="conduct </script>", output="<b>x</b>", exit=None, error="was not run")
    html = podium.view([], NOW, error="conduct status failed", entries=[nasty])
    assert "<h2>Activity</h2>" in html and "<b>" not in html and "</script>" not in html
    assert '<span class="badge alert">not run</span>' in html and "&lt;b&gt;x&lt;/b&gt;was not run" in html


def test_the_page_has_one_dialog_that_previews_then_sends_with_the_token_in_the_body():
    html = podium.page("<p>THE VIEW</p>")
    assert '<dialog id="act"' in html and '<button type="button" id="act-go">Preview</button>' in html
    assert '<button type="button" id="act-cancel">Cancel</button>' in html
    assert 'post("/preview", {action: action})' in html and 'post("/run", {ticket: ticket})' in html
    assert 'method: "POST"' in html and "body.t = token" in html
    assert "Dream first?" in html                           # asked before any Stop
    assert "if (!dialog.open) { refresh(); }" in html       # the page does not change under an open dialog
    assert html.count("innerHTML") == 1                     # only the view, which podium itself made, is put in whole
    assert "http://" not in html and "https://" not in html


def test_the_dialog_says_what_it_is_waiting_for_and_for_how_long_while_conduct_runs():
    html = podium.page("<p>THE VIEW</p>")
    assert ('<p id="act-progress" class="progress" role="status" hidden><span class="spin"></span>'
            '<span id="act-progress-text"></span></p>') in html
    assert '"Asking conduct what it would do"' in html and '"Sending: "' in html
    assert "setInterval(tick, 1000)" in html and "clearInterval(ticking)" in html
    assert "@keyframes spin" in html and "prefers-reduced-motion: reduce" in html
    assert '"Working' not in html                     # the button no longer carries the only sign of life


def test_a_line_leaves_out_what_is_only_the_usual_no_mail_normal_pace_nobody_on_duty():
    quiet = podium.view([row("lone-tools", "off")], NOW)
    assert '<ul class="facts"><li>opus, high</li></ul>' in quiet
    for usual in ("nobody on duty", "pace normal", "0 new", "0 open"):
        assert usual not in quiet
    busy = podium.view([row("lone-tools", "running", duty="mac", minutes=0, pace="relaxed", open_=3)], NOW)
    assert '<ul class="facts"><li>mac, just now</li><li>pace relaxed</li><li>3 open</li><li>opus, high</li></ul>' in busy
    bare = podium.view([row("old-thing", "off", kind=None, refused="no lobster.conf")], NOW)
    assert '<span class="badge off">off</span><p class="refused">' in bare and "<ul" not in bare


def test_the_page_wears_the_site_s_colours_typeface_and_roundel():
    html = podium.page("<p>THE VIEW</p>")
    for colour in ("#F4F0EE", "#FFFFFF", "#333333", "#6E6661", "#DED5CE", "#D15727", "#A6451F", "#F3D2C2", "#A51E22",
                   "#3B7A55"):
        assert colour in html
    assert '"EB Garamond", Georgia, serif' in html
    assert '<span class="mark" aria-hidden="true">P</span><h1>podium</h1>' in html
    assert "url(" not in html and "@import" not in html        # no font or image is fetched from anywhere


def test_a_hidden_part_of_the_page_stays_hidden_whatever_its_own_style_says():
    # the progress line is laid out as a row, which would otherwise show it while it is marked hidden
    assert "[hidden] { display: none !important; }" in podium.page("")
