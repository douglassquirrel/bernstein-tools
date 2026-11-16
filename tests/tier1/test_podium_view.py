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


def card_shapes(g):
    """Each card as (its project, its full claw lines, its labels), by name and what each is to the card."""
    return [(head["mailbox"], [(c["mailbox"], label) for c, label in claws],
             [(c["mailbox"], label) for c, label in labels]) for head, claws, labels in g["cards"]]


def test_rows_are_grouped_a_card_per_non_code_project_then_the_claws_then_the_rest_then_bernstein():
    g = podium.groups(a_factory())
    assert card_shapes(g) == [
        ("menus", [], [("video-tools", "home claw")]),
        ("recipes", [("recipes-tools", "home claw"), ("gone-tools", "claw")], [("video-tools", "claw")])]
    assert [(r["mailbox"], said) for r, said in g["claws"]] == [
        ("lone-tools", "code"), ("video-tools", "home claw of menus, used by recipes")]
    assert [r["mailbox"] for r in g["unstartable"]] == ["old-thing"]
    assert g["bernstein"]["mailbox"] == "bernstein"


def test_a_claw_named_by_a_project_but_with_no_mailbox_is_shown_as_such():
    g = podium.groups(a_factory())
    gone = g["cards"][1][1][1][0]
    assert gone == {"mailbox": "gone-tools", "missing": True}


def test_groups_with_nothing_in_them_are_empty_and_bernstein_may_be_absent():
    assert podium.groups([]) == {"cards": [], "claws": [], "unstartable": [], "bernstein": None, "conductors": []}


def ganglia(*named, tools=("a-tools", "b-tools", "c-tools")):
    """Non-code projects g1, g2, … each naming (its home claw, [its further claws]), and the tools projects
    with what conduct status says of them: whom they serve."""
    rows = [row(f"g{i}", "running", kind="non-code", duty="mac", sister=home, claws=([home] if home else []) + list(more))
            for i, (home, more) in enumerate(named, 1)]
    for name in tools:
        rows.append(row(name, "off", serves=[r["mailbox"] for r in rows if name in r["claws"]]))
    return rows


def test_a_tools_project_two_ganglia_name_as_a_further_claw_is_a_label_on_each_card_and_one_line_in_claws():
    g = podium.groups(ganglia(("", ["a-tools"]), ("", ["a-tools"])))
    assert card_shapes(g) == [("g1", [], [("a-tools", "claw")]), ("g2", [], [("a-tools", "claw")])]
    assert [(r["mailbox"], said) for r, said in g["claws"]] == [
        ("a-tools", "used by g1 and g2"), ("b-tools", "code"), ("c-tools", "code")]


def test_a_tools_project_three_ganglia_name_says_all_three_and_is_a_label_on_each():
    g = podium.groups(ganglia(("", ["a-tools"]), ("", ["a-tools"]), ("", ["a-tools"])))
    assert [labels for _head, _claws, labels in card_shapes(g)] == [[("a-tools", "claw")]] * 3
    assert {r["mailbox"]: said for r, said in g["claws"]}["a-tools"] == "used by g1, g2 and g3"


def test_a_further_claw_only_one_ganglion_names_is_in_claws_and_a_label_on_its_card():
    g = podium.groups(ganglia(("", ["a-tools"])))
    assert card_shapes(g) == [("g1", [], [("a-tools", "claw")])]
    assert {r["mailbox"]: said for r, said in g["claws"]}["a-tools"] == "used by g1"


def test_the_home_claw_of_two_ganglia_is_one_line_in_claws_and_a_home_claw_label_on_each_card():
    g = podium.groups(ganglia(("a-tools", []), ("a-tools", [])))
    assert card_shapes(g) == [("g1", [], [("a-tools", "home claw")]), ("g2", [], [("a-tools", "home claw")])]
    assert {r["mailbox"]: said for r, said in g["claws"]}["a-tools"] == "home claw of g1 and g2"


def test_the_home_claw_of_one_ganglion_that_another_names_as_a_claw_goes_to_claws_saying_both():
    g = podium.groups(ganglia(("a-tools", []), ("b-tools", ["a-tools"])))
    assert card_shapes(g) == [("g1", [], [("a-tools", "home claw")]),
                              ("g2", [("b-tools", "home claw")], [("a-tools", "claw")])]
    assert [(r["mailbox"], said) for r, said in g["claws"]] == [
        ("a-tools", "home claw of g1, used by g2"), ("c-tools", "code")]


def test_a_home_claw_nobody_else_names_stays_a_full_line_on_its_card_and_is_not_in_claws():
    g = podium.groups(ganglia(("a-tools", [])))
    assert card_shapes(g) == [("g1", [("a-tools", "home claw")], [])]
    assert [r["mailbox"] for r, _said in g["claws"]] == ["b-tools", "c-tools"]


def test_the_claws_section_is_in_order_of_name_whatever_order_conduct_lists_them_in():
    rows = ganglia(("", ["c-tools", "a-tools"]), tools=("c-tools", "b-tools", "a-tools"))
    assert [r["mailbox"] for r, _said in podium.groups(rows)["claws"]] == ["a-tools", "b-tools", "c-tools"]


def test_the_view_says_when_it_was_made_and_lays_out_cards_then_sections():
    html = podium.view(a_factory(), NOW)
    assert '<p class="asof">As of 09:40:05 UTC</p>' in html
    order = [html.index(mark) for mark in (
        '<span class="name">menus</span>', '<span class="name">recipes</span>', "<h2>Claws</h2>",
        '<span class="name">lone-tools</span>', "<h2>Cannot be started</h2>", '<span class="name">old-thing</span>',
        "<h2>bernstein</h2>", '<span class="name">bernstein</span>')]
    assert order == sorted(order)
    assert html.count('<section class="card">') == 5      # menus, recipes, claws, cannot be started, bernstein


def test_a_row_shows_its_kind_badge_duty_pace_mail_and_model():
    html = podium.view([row("recipes", "running", kind="non-code", duty="mac", minutes=3, pace="eager", new=2,
                            open_=1, sister="recipes-tools", claws=["recipes-tools"]),
                        row("recipes-tools", "handed-over", sister="recipes", serves=["recipes"])], NOW)
    assert ('<div class="row"><div class="who"><span class="name">recipes</span> <span class="kind">non-code</span>'
            '</div><span class="badge ok">running</span><ul class="facts"><li>Claude Code, 3 min ago</li>'
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
    assert "<h2>Claws</h2>" in html and "Cannot be started" not in html and "<h2>bernstein</h2>" not in html
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


WAITS = ("This session is not watching mail (a Claude Cowork session, or one whose watch has stopped): it wakes "
         "when you next type to it.")
SOME_WAIT = ("Some of these sessions are not watching mail (a Claude Cowork session, or one whose watch has "
             "stopped): each of those wakes when you next type to it.")


def test_the_view_has_a_bar_of_buttons_for_everything_at_once_only_when_one_applies():
    html = podium.view(a_factory(), NOW)        # menus and recipes are running, video-tools is stale
    assert ('<div class="all"><button type="button" class="act" data-verb="stop" data-all="1">Stop all</button>'
            '<button type="button" class="act" data-verb="dormant" data-all="1">Dormant all</button>'
            '<button type="button" class="act" data-verb="dream" data-all="1">Dream all</button>'
            '<button type="button" class="act" data-verb="wake" data-all="1" data-note="' + SOME_WAIT + '" title="'
            + SOME_WAIT + '">Wake all</button></div>') in html      # video-tools is stale: its Wake will wait
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


def test_the_page_has_one_dialog_that_sends_at_once_with_the_token_in_the_body_and_no_preview():
    html = podium.page("<p>THE VIEW</p>")
    assert '<dialog id="act"' in html and '<button type="button" id="act-go">Send</button>' in html
    assert '<button type="button" id="act-cancel">Cancel</button>' in html
    assert 'post("/run", {action: action})' in html
    assert "preview" not in html.lower() and "ticket" not in html and "dry-run" not in html and "dry run" not in html
    assert "Nothing has been sent" not in html
    # after a Start that worked the box closes by itself: the app has come to the front by then
    assert 'if (action.verb === "start" && got.said.exit === 0) { dialog.close(); return; }' in html
    assert 'method: "POST"' in html and "body.t = token" in html
    assert "Dream first?" in html                           # asked before any Stop
    assert "if (!dialog.open) { refresh(); }" in html       # the page does not change under an open dialog
    assert html.count("innerHTML") == 1                     # only the view, which podium itself made, is put in whole
    assert "http://" not in html and "https://" not in html


def test_the_dialog_says_what_it_is_waiting_for_and_for_how_long_while_conduct_runs():
    html = podium.page("<p>THE VIEW</p>")
    assert ('<p id="act-progress" class="progress" role="status" hidden><span class="spin"></span>'
            '<span id="act-progress-text"></span></p>') in html
    assert '"Sending: " + title.textContent' in html and "Asking conduct what it would do" not in html
    assert '" (it waits up to " + action.wait + " s for the handover)"' in html
    assert "setInterval(tick, 1000)" in html and "clearInterval(ticking)" in html
    assert "@keyframes spin" in html and "prefers-reduced-motion: reduce" in html
    assert '"Working' not in html                     # the button no longer carries the only sign of life


def test_a_line_leaves_out_what_is_only_the_usual_no_mail_normal_pace_nobody_on_duty():
    quiet = podium.view([row("lone-tools", "off")], NOW)
    assert '<ul class="facts"><li>opus, high</li></ul>' in quiet
    for usual in ("nobody on duty", "pace normal", "0 new", "0 open"):
        assert usual not in quiet
    busy = podium.view([row("lone-tools", "running", duty="mac", minutes=0, pace="relaxed", open_=3)], NOW)
    assert '<ul class="facts"><li>Claude Code, just now</li><li>pace relaxed</li><li>3 open</li><li>opus, high</li></ul>' in busy
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


LINK = "claude://claude.ai/epitaxy/local_11111111-1111-4111-8111-111111111111"


def with_session(r, link=LINK):
    return dict(r, session={"id": link.rsplit("/", 1)[-1], "link": link, "last_activity": "2026-10-18T09:38:00Z"})


def test_a_row_whose_project_has_a_session_in_the_desktop_app_links_to_it():
    html = podium.view([with_session(row("lone-tools", "running", duty="mac"))], NOW)
    assert ('<div class="acts"><a class="open" href="' + LINK + '" title="Open its newest session in the Claude app '
            '(last active 09:38 UTC)">Open</a><button type="button" class="act" data-verb="stop"') in html
    assert "Open</a>" not in podium.view([row("lone-tools", "running", duty="mac")], NOW)


def test_bernstein_s_own_row_and_a_row_with_no_buttons_still_get_the_link():
    html = podium.view([with_session(row("bernstein", "running", kind=None, duty="mac")),
                        with_session(row("old-thing", "off", kind=None, refused="no lobster.conf"))], NOW)
    assert html.count('<div class="acts"><a class="open" href="' + LINK + '"') == 2
    assert "<button" not in html


def test_a_link_that_is_not_the_app_s_own_kind_is_never_put_on_the_page():
    for bad in ("javascript:alert(1)", "https://example.com/", "claude://claude.ai/epitaxy/local_x\" onclick=\"y",
                "claude://elsewhere/local_11111111-1111-4111-8111-111111111111", LINK + "/../x", "", None, 7):
        html = podium.view([with_session(row("lone-tools", "off"), link=LINK) | {"session": {"link": bad}}], NOW)
        assert "Open</a>" not in html and "href" not in html
    assert "Open</a>" not in podium.view([dict(row("lone-tools", "off"), session="x")], NOW)


def test_a_cowork_session_s_link_is_shown_too_with_no_time():
    link = "claude://claude.ai/cowork/session_01AAAAAAAAAAAAAAAAAAAAAA"
    r = dict(row("recipes", "running", kind="non-code", duty="device"),
             session={"id": link.rsplit("/", 1)[-1], "link": link, "app": "cowork", "last_activity": None})
    html = podium.view([r], NOW)
    assert ('<a class="open" href="' + link + '" title="Open its newest session in the Claude app">Open</a>') in html
    for bad in ("claude://claude.ai/cowork/local_11111111-1111-4111-8111-111111111111", link + "?x=1",
                "claude://claude.ai/cowork/session_", "claude://claude.ai/cowork/session_01AAAA/../x"):
        assert "Open</a>" not in podium.view([dict(r, session={"link": bad})], NOW)


def test_the_session_on_duty_is_named_by_the_app_it_runs_in_not_by_its_mail_name():
    assert "<li>Claude Code, 3 min ago</li>" in podium.view([row("lone-tools", "running", duty="mac")], NOW)
    assert "<li>Claude Cowork, 3 min ago</li>" in podium.view(
        [row("recipes", "running", kind="non-code", duty="device")], NOW)
    other = podium.view([row("lone-tools", "running", duty="desk-1 <b>")], NOW)       # any other name is shown as it is
    assert "<li>desk-1 &lt;b&gt;, 3 min ago</li>" in other
    assert podium.session_name("mac") == "Claude Code" and podium.session_name("device") == "Claude Cowork"
    assert podium.session_name(None) == "None"


def an_orchestra():
    """a_factory's rows and, as conduct status lists them, a conductor and its claw."""
    return a_factory() + [
        row("maestro", "running", kind="conductor", duty="mac", sister="maestro-tools", claws=["maestro-tools"]),
        row("maestro-tools", "off", sister="maestro", serves=["maestro"]),
    ]


def test_a_conductor_and_its_claw_are_one_card_and_neither_in_claws_nor_unstartable():
    g = podium.groups(an_orchestra())
    assert [(head["mailbox"], [(c["mailbox"], label) for c, label in claws]) for head, claws in g["conductors"]] == [
        ("maestro", [("maestro-tools", "claw")])]
    assert [r["mailbox"] for r, _said in g["claws"]] == ["lone-tools", "video-tools"]
    assert [r["mailbox"] for r in g["unstartable"]] == ["old-thing"]
    assert [head["mailbox"] for head, _claws, _labels in g["cards"]] == ["menus", "recipes"]
    assert g["bernstein"]["mailbox"] == "bernstein"


def test_the_mailbox_bernstein_once_it_is_a_conductor_is_shown_as_one_with_its_claw_under_it():
    rows = [row("bernstein", "running", kind="conductor", duty="mac", sister="bernstein-tools", claws=["bernstein-tools"]),
            row("bernstein-tools", "running", duty="mac", sister="bernstein", serves=["bernstein"]),
            row("gone", "off", kind="conductor", sister="gone-tools", claws=["gone-tools"])]
    g = podium.groups(rows)
    assert (g["bernstein"], g["claws"], g["unstartable"], g["cards"]) == (None, [], [], [])
    assert [(head["mailbox"], [(c["mailbox"], c.get("missing", False)) for c, _label in claws])
            for head, claws in g["conductors"]] == [("bernstein", [("bernstein-tools", False)]),
                                                    ("gone", [("gone-tools", True)])]
    html = podium.view(rows, NOW)
    assert "<h2>bernstein</h2>" not in html and "<h2>Claws</h2>" not in html
    assert html.count("<h2>Conductor</h2>") == 1 and html.count('<section class="card">') == 2
    card = html[html.index("<h2>Conductor</h2>"):]
    assert card.index('<span class="name">bernstein</span> <span class="kind">conductor</span>') < card.index(
        '<div class="row claw"><div class="who"><span class="name">bernstein-tools</span> <span class="kind">claw</span>')


def test_the_conductors_card_comes_last_under_its_own_heading():
    html = podium.view(an_orchestra(), NOW)
    order = [html.index(mark) for mark in (
        '<span class="name">recipes</span>', "<h2>Claws</h2>", "<h2>Cannot be started</h2>",
        "<h2>bernstein</h2>", "<h2>Conductor</h2>", '<span class="name">maestro</span>',
        '<span class="name">maestro-tools</span>')]
    assert order == sorted(order)
    assert html.count('<span class="name">maestro-tools</span>') == 1
    assert html.count('<section class="card">') == 6


def test_a_conductor_has_no_button_in_any_state_and_is_not_counted_for_the_buttons_for_all():
    for state in ("off", "handed-over", "running", "dormant", "quiet", "stale"):
        assert podium.buttons(row("maestro", state, kind="conductor", duty="mac", sister="maestro-tools")) == []
    assert podium.buttons(row("maestro-tools", "off", sister="maestro", serves=["maestro"])) == ["start"]
    assert podium.buttons(row("maestro-tools", "running", duty="mac", sister="maestro", serves=["maestro"])) == [
        "stop", "dormant", "dream"]
    assert podium.buttons_for_all([row("maestro", "running", kind="conductor", duty="mac"),
                                   row("other", "stale", kind="conductor", duty="mac"), row("a-tools", "off")]) == []
    html = podium.view(an_orchestra(), NOW)
    assert 'data-project="maestro"' not in html and 'data-project="maestro-tools"' in html



def test_a_start_that_worked_carries_its_reminder_in_the_activity_since_its_box_has_closed():
    remind = "Now in the desktop app: confirm the <folder>, then send the first line."
    html = podium.view([], NOW, entries=[dict(RUNS[0], reminder=remind), dict(RUNS[0], reminder=None)])
    assert html.count('<p class="remind">') == 1
    assert '<p class="remind">Now in the desktop app: confirm the &lt;folder&gt;, then send the first line.</p>' in html
    assert ".remind {" in podium.PAGE


def filling(r, tokens=135719, window=1000000, percent=14, warn=False, as_of="2026-10-18T09:30:07Z"):
    """A row with a session whose context window conduct could read."""
    return dict(with_session(r), context={"tokens": tokens, "window": window, "percent": percent, "as_of": as_of,
                                          "warn": warn})


def bar(percent, fill=None):
    """The bar and the figure beside it, as the page draws them: fill is the bar's filled length out of 100."""
    fill = percent if fill is None else fill
    return ('<svg class="bar" viewBox="0 0 100 8" preserveAspectRatio="none" role="img" '
            f'aria-label="{percent}% of context"><rect class="fill" width="{fill}" height="8"/></svg>'
            f'<span aria-hidden="true">{percent}%</span></li>')


def test_a_row_draws_how_full_its_session_s_context_window_is_as_a_bar_with_the_bare_percentage_beside_it():
    html = podium.view([filling(row("lone-tools", "running", duty="mac"))], NOW)
    assert ('<li>opus, high</li><li class="context" title="14% of context: 135,719 tokens in use at 09:30 UTC, '
            'of a window of 1,000,000 (the setting CONTEXT_WINDOW)">' + bar(14) + '</ul>') in html
    assert "of context (" not in html and "(of 1,000,000)" not in html      # the words have left the line


@pytest.mark.parametrize("percent, fill", [(0, 0), (1, 1), (50, 50), (59, 59), (60, 60), (99, 99), (100, 100),
                                           (101, 100), (150, 100), (100000, 100)])
def test_the_bar_fills_with_the_percentage_and_never_overflows_while_the_figure_says_the_real_one(percent, fill):
    html = podium.view([filling(row("lone-tools"), percent * 10, 1000, percent, percent >= 60)], NOW)
    assert bar(percent, fill) in html
    assert html.count("<svg") == 1 and html.count('<rect class="fill" width="') == 1


def test_a_session_at_or_over_the_warning_level_has_a_red_bar_and_is_not_marked_by_colour_alone():
    html = podium.view([filling(row("lone-tools", "running", duty="mac"), 600000, 1000000, 60, True)], NOW)
    assert ('<li class="context warn" title="60% of context: 600,000 tokens in use at 09:30 UTC, of a window of '
            '1,000,000 (the setting CONTEXT_WINDOW); at or over the warning level (the setting CONTEXT_WARN)">'
            + bar(60)) in html
    calm = podium.view([filling(row("lone-tools", "running", duty="mac"), 590000, 1000000, 59, False)], NOW)
    assert 'class="context warn"' not in calm and '<li class="context" title="59% of context: 590,000 tokens' in calm
    page = podium.page("")
    assert ".facts .context.warn .bar { border-color: var(--mistake-text); }" in page       # the bar is red:
    assert ".facts .context.warn .fill { fill: var(--mistake-text); }" in page              # its outline and its fill
    assert (".facts .context.warn { color: var(--ink); font-weight: 600; border: 2px solid var(--gold);" in page)
    assert ".facts .context .fill { fill: var(--muted); }" in page                          # and not red below it


def test_the_mark_is_conduct_s_to_give_and_the_page_never_works_it_out_for_itself():
    full = podium.view([filling(row("lone-tools"), 990000, 1000000, 99, False)], NOW)
    assert '<li class="context" title="99% of context: 990,000 tokens' in full and "context warn" not in full
    early = podium.view([filling(row("lone-tools"), 20000, 1000000, 2, True)], NOW)
    assert '<li class="context warn" title="2% of context: 20,000 tokens' in early


def test_a_row_with_a_session_whose_context_cannot_be_told_says_not_known_and_one_with_no_session_says_nothing():
    known_not = '<li class="context unknown">context not known</li>'
    assert known_not in podium.view([dict(with_session(row("lone-tools", "running", duty="mac")), context=None)], NOW)
    assert known_not in podium.view([with_session(row("lone-tools"))], NOW)       # an older conduct: no key at all
    for r in (row("lone-tools", "running", duty="mac"), dict(row("lone-tools"), session=None, context=None),
              dict(row("lone-tools"), session=None, context={"tokens": 5, "window": 1000, "percent": 1,
                                                             "as_of": None, "warn": False})):
        assert "context" not in podium.view([r], NOW) and "<svg" not in podium.view([r], NOW)


def test_not_known_has_no_bar_so_it_is_never_taken_for_an_empty_one():
    empty = podium.view([filling(row("lone-tools"), 0, 1000000, 0, False)], NOW)
    unknown = podium.view([dict(with_session(row("lone-tools")), context=None)], NOW)
    assert bar(0) in empty and "context not known" not in empty
    assert "<svg" not in unknown and "0%" not in unknown and "context not known" in unknown


def test_the_page_still_makes_itself_when_no_session_has_a_figure_and_then_has_no_bar_at_all():
    rows = [dict(with_session(row("recipes-tools", "running", duty="mac")), context=None),
            dict(with_session(row("word-tools")), context=None), row("video-tools")]
    html = podium.view(rows, NOW)
    assert html.count("context not known") == 2 and "<svg" not in html and "<rect" not in html
    assert '<span class="name">video-tools</span>' in html
    assert "<svg" not in podium.page(html)


@pytest.mark.parametrize("change", [
    {"percent": "14"}, {"percent": 14.0}, {"percent": True}, {"percent": -1}, {"percent": None},
    {"tokens": "135719"}, {"tokens": None}, {"tokens": -5}, {"window": 0}, {"window": "1000000"}, {"window": None},
    {"warn": "yes"}, {"warn": None}, {"warn": 1},
    {"percent": "<script>alert(1)</script>"}, {"percent": '100"/><script>'},
])
def test_a_context_that_is_not_the_shape_conduct_gives_is_shown_as_not_known_never_as_given(change):
    r = filling(row("lone-tools", "running", duty="mac"))
    r["context"].update(change)
    html = podium.view([r], NOW)
    assert '<li class="context unknown">context not known</li>' in html
    assert "% of context" not in html and "<script>" not in html and "<svg" not in html
    for odd in ("a string", ["a", "list"], 14, True):
        assert '<li class="context unknown">context not known</li>' in podium.view([dict(r, context=odd)], NOW)


def test_the_hover_gives_the_detail_word_for_word_as_before_after_the_words_that_left_the_line():
    html = podium.view([filling(row("lone-tools"))], NOW)
    before = "135,719 tokens in use at 09:30 UTC, of a window of 1,000,000 (the setting CONTEXT_WINDOW)"
    assert f'title="14% of context: {before}">' in html
    marked = podium.view([filling(row("lone-tools"), 600000, 1000000, 60, True)], NOW)
    assert ('title="60% of context: 600,000 tokens in use at 09:30 UTC, of a window of 1,000,000 (the setting '
            'CONTEXT_WINDOW); at or over the warning level (the setting CONTEXT_WARN)">') in marked


def test_the_time_the_figure_is_true_for_names_the_day_when_it_is_not_today_and_is_left_out_when_it_is_no_time():
    old = podium.view([filling(row("lone-tools"), as_of="2026-10-16T22:04:37Z")], NOW)
    assert ('title="14% of context: 135,719 tokens in use at 22:04 UTC on 16 October 2026, of a window of '
            '1,000,000 (') in old
    for odd in (None, "yesterday", 7, '"><script>'):
        html = podium.view([filling(row("lone-tools"), as_of=odd)], NOW)
        assert ('title="14% of context: 135,719 tokens in use, of a window of 1,000,000 (the setting '
                'CONTEXT_WINDOW)"><svg') in html
        assert "<script>" not in html


def test_a_figure_over_the_whole_window_is_said_as_it_is_in_the_figure_and_in_the_hover():
    html = podium.view([filling(row("lone-tools"), 1500, 1000, 150, True)], NOW)
    assert 'title="150% of context: 1,500 tokens in use at 09:30 UTC, of a window of 1,000 (' in html
    assert bar(150, 100) in html


def test_the_bar_wears_the_page_s_own_colours_and_has_a_size_of_its_own():
    page = podium.page("")
    assert ".facts .context .bar { width: 3.5rem; height: 0.5rem;" in page
    assert "border: 1px solid var(--muted);" in page
    assert ".facts .context { display: inline-flex; align-items: center; gap: 6px; }" in page
    assert ".facts .context .of" not in page                       # the size is no longer on the line


def wake_button(name, note=None):
    said = f' data-note="{note}" title="{note}"' if note else ""
    return f'<button type="button" class="act" data-verb="wake" data-project="{name}"{said}>Wake</button>'


def test_the_wake_of_a_dormant_session_on_the_mac_that_is_watching_is_a_plain_button():
    html = podium.view([row("lone-tools", "dormant", duty="mac", reported={"status": "dormant"})], NOW)
    assert wake_button("lone-tools") in html and "data-note" not in html and "not watching mail" not in html


@pytest.mark.parametrize("state, holder", [("dormant", "device"), ("quiet", "device"), ("stale", "device"),
                                           ("quiet", "mac"), ("stale", "mac"), ("dormant", "laptop")])
def test_the_wake_of_a_session_that_is_not_watching_says_it_wakes_when_he_next_types_to_it(state, holder):
    html = podium.view([row("lone-tools", state, duty=holder, reported={"status": "dormant"})], NOW)
    assert wake_button("lone-tools", WAITS) in html


def test_a_dormant_session_on_the_mac_whose_duty_has_gone_stale_is_not_watching_either():
    r = row("lone-tools", "dormant", duty="mac", reported={"status": "dormant"})
    r["duty"]["stale"] = True
    assert wake_button("lone-tools", WAITS) in podium.view([r], NOW)


def test_only_a_wake_carries_the_note_never_another_button():
    html = podium.view([row("a-tools", "running", duty="device"), row("b-tools", "off"),
                        row("c-tools", "dormant", duty="device")], NOW)
    assert html.count("data-note=") == 2                       # c-tools' Wake, and Wake all
    for verb in ("stop", "dormant", "dream", "start"):
        assert f'data-verb="{verb}" data-project="' in html and f'data-verb="{verb}" data-note' not in html


def test_wake_all_carries_the_note_only_when_some_session_asleep_is_not_watching():
    watching = [row("a-tools", "dormant", duty="mac"), row("b-tools", "running", duty="mac")]
    assert '<button type="button" class="act" data-verb="wake" data-all="1">Wake all</button>' in podium.view(watching, NOW)
    mixed = watching + [row("recipes", "dormant", kind="non-code", duty="device", sister="b-tools", claws=("b-tools",))]
    assert ('<button type="button" class="act" data-verb="wake" data-all="1" data-note="' + SOME_WAIT + '" title="'
            + SOME_WAIT + '">Wake all</button>') in podium.view(mixed, NOW)
    # bernstein's own session and a conductor's are never woken by Wake all, so they never bring the note
    own = watching + [row("bernstein", "dormant", kind=None, duty="device"),
                      row("maestro", "dormant", kind="conductor", duty="device")]
    assert "data-note" not in podium.view(own, NOW)


def test_the_dialog_shows_a_wake_s_note_before_it_is_sent_and_as_text_never_markup():
    html = podium.page("<p>THE VIEW</p>")
    assert '<p id="act-waits" class="note" hidden></p>' in html
    assert ('open(pressed.dataset.verb, pressed.dataset.project, pressed.dataset.all === "1", '
            'pressed.dataset.note)') in html
    assert 'waits.textContent = why || "";' in html and "waits.hidden = !why;" in html
    assert html.count("innerHTML") == 1


def test_a_cowork_session_that_is_awake_does_not_bring_the_note_to_wake_all():
    rows = [row("a-tools", "dormant", duty="mac"), row("recipes", "running", kind="non-code", duty="device")]
    html = podium.view(rows, NOW)
    assert '<button type="button" class="act" data-verb="wake" data-all="1">Wake all</button>' in html
    assert "data-note" not in html


def a_label(name, what, words, tone):
    return (f'<a class="label" href="#claw-{name}" aria-label="{name}, {what}, {words}">{name} '
            f'<span class="kind">{what}</span> <span class="badge {tone}">{words}</span></a>')


def card_of(html, name):
    """The card whose own line is the named project's."""
    start = html.index(f'<span class="name">{name}</span> <span class="kind">non-code</span>')
    return html[html.rindex('<section class="card">', 0, start):html.index("</section>", start)]


def test_each_card_names_a_shared_claw_by_a_label_linked_to_its_one_line_in_claws_which_says_who_uses_it():
    html = podium.view(ganglia(("", ["a-tools"]), ("", ["a-tools"])), NOW)
    label = a_label("a-tools", "claw", "off", "off")
    assert card_of(html, "g1").endswith(f'<div class="labels">{label}</div>')
    assert card_of(html, "g2").endswith(f'<div class="labels">{label}</div>')
    assert ('<div class="row" id="claw-a-tools"><div class="who"><span class="name">a-tools</span> '
            '<span class="kind">used by g1 and g2</span></div>') in html
    assert html.count('data-project="a-tools"') == 1 and html.count('id="claw-a-tools"') == 1


def test_a_home_claw_label_says_home_claw_and_a_line_nobody_points_to_has_no_anchor():
    html = podium.view(ganglia(("a-tools", []), ("a-tools", ["b-tools"])), NOW)
    assert a_label("a-tools", "home claw", "off", "off") in card_of(html, "g1")
    assert card_of(html, "g2").endswith(
        f'<div class="labels">{a_label("a-tools", "home claw", "off", "off")}{a_label("b-tools", "claw", "off", "off")}'
        '</div>')
    assert '<span class="kind">home claw of g1 and g2</span>' in html
    assert '<div class="row"><div class="who"><span class="name">c-tools</span> <span class="kind">code</span>' in html


def test_a_card_with_no_claws_drawn_elsewhere_has_no_row_of_labels():
    html = podium.view(ganglia(("a-tools", []), ("", [])), NOW)
    assert '<div class="labels">' not in html and 'class="label"' not in html
    assert '<div class="row claw"><div class="who"><span class="name">a-tools</span> <span class="kind">home claw</span>' \
        in card_of(html, "g1")


@pytest.mark.parametrize("state, reported, words, tone", [
    ("running", None, "running", "ok"), ("dormant", None, "dormant", "sleep"), ("quiet", None, "quiet", "warn"),
    ("stale", None, "stale", "alert"), ("handed-over", None, "handed over", "off"), ("off", None, "off", "off"),
    ("running", DREAMING, "dreaming until 10:20 UTC", "busy"),
])
def test_a_label_gives_its_project_s_state_in_the_badge_s_own_words_and_tone(state, reported, words, tone):
    rows = ganglia(("", ["a-tools"]), ("", ["a-tools"]))
    rows[2] = dict(row("a-tools", state, duty="mac" if state != "off" else None, reported=reported),
                   serves=["g1", "g2"])
    html = podium.view(rows, NOW)
    assert html.count(a_label("a-tools", "claw", words, tone)) == 2
    assert f'<span class="badge {tone}">{words}</span>' in html[html.index('id="claw-a-tools"'):]


def test_a_label_points_to_the_line_wherever_it_is_a_conductor_s_card_or_cannot_be_started():
    rows = [row("g1", "running", kind="non-code", duty="mac", claws=["maestro-tools", "old-tools"]),
            row("maestro", "running", kind="conductor", duty="mac", sister="maestro-tools", claws=["maestro-tools"]),
            row("maestro-tools", "off", sister="maestro", serves=["g1", "maestro"]),
            row("old-tools", "off", kind=None, refused="/p/old-tools has no lobster.conf")]
    html = podium.view(rows, NOW)
    assert card_of(html, "g1").endswith(
        f'<div class="labels">{a_label("maestro-tools", "claw", "off", "off")}{a_label("old-tools", "claw", "off", "off")}'
        '</div>')
    assert '<div class="row claw" id="claw-maestro-tools"><div class="who"><span class="name">maestro-tools</span>' in html
    assert '<div class="row" id="claw-old-tools"><div class="who"><span class="name">old-tools</span>' in html
    assert html.count('<span class="name">old-tools</span>') == 1 and "<h2>Claws</h2>" not in html


def test_a_label_s_name_and_state_are_text_never_markup():
    odd = 'x"<b>&é'
    rows = [row("g1", "running", kind="non-code", duty="mac", claws=[odd]), row("g2", "off", kind="non-code", claws=[odd]),
            row(odd, "running", duty="mac", serves=["g1", "g2"],
                reported={"status": "<i>busy</i>", "set": "2026-10-18T09:20:00Z", "until": None})]
    html = podium.view(rows, NOW)
    safe = "x&quot;&lt;b&gt;&amp;é"
    assert (f'<a class="label" href="#claw-{safe}" aria-label="{safe}, claw, &lt;i&gt;busy&lt;/i&gt;">{safe} '
            '<span class="kind">claw</span> <span class="badge busy">&lt;i&gt;busy&lt;/i&gt;</span></a>') in html
    assert f'id="claw-{safe}"' in html and "<b>" not in html and "<i>" not in html


def test_labels_wrap_wear_the_page_s_own_colours_and_the_line_a_label_leads_to_is_shown_where_it_is():
    page = podium.page("")
    assert ".labels { display: flex; flex-wrap: wrap;" in page
    assert "a.label { display: inline-flex; align-items: center;" in page and "color: var(--ink);" in page
    label = page[page.index("a.label {"):]
    assert "flex-wrap: wrap; white-space: nowrap;" in label[:label.index("}")]     # a name never breaks at its hyphen
    assert "a.label .badge { font-size: 13px; white-space: normal; }" in page        # a long state still wraps
    assert "a.label:focus-visible { outline: 2px solid var(--accent);" in page
    assert ".row:target { background: var(--tint); }" in page
    assert "  .labels { padding-left: 24px; }" in page[page.index("@media (max-width: 640px)"):]


def every_naming(tools):
    """Every way one ganglion can name the tools projects: a home claw or none, and any further claws."""
    for home in ("",) + tools:
        rest = [t for t in tools if t != home]
        for mask in range(2 ** len(rest)):
            yield home, [t for i, t in enumerate(rest) if mask >> i & 1]


@pytest.mark.parametrize("ganglia_count, tools, conductor", [
    (3, ("a-tools", "b-tools"), False), (2, ("a-tools", "b-tools", "c-tools"), False),
    (2, ("a-tools", "b-tools", "c-tools"), True),       # a-tools is also the claw of a conductor
])
def test_over_every_way_ganglia_can_name_claws_each_mailbox_has_one_line_and_one_set_of_buttons(
        ganglia_count, tools, conductor):
    import itertools
    ways = list(every_naming(tools))
    for named in itertools.product(ways, repeat=ganglia_count):
        rows = ganglia(*named, tools=tools)
        if conductor:
            rows.append(row("maestro", "running", kind="conductor", duty="mac", sister="a-tools", claws=["a-tools"]))
            rows[ganglia_count]["serves"].append("maestro")
        lines = podium.view(rows, NOW).split('<div class="row')[1:]
        for r in rows:
            name = r["mailbox"]
            full = [ln for ln in lines if f'<span class="name">{name}</span>' in ln]
            assert len(full) == 1, (named, name)
            with_buttons = 0 if r["kind"] == "conductor" else 1        # a conductor's line never has any
            assert sum(f'data-project="{name}"' in ln for ln in lines) == with_buttons, (named, name)


def test_who_uses_a_claw_wraps_under_its_name_rather_than_being_cut_off():
    page = podium.page("")
    rule = page[page.index(".kind {"):]
    assert rule[:rule.index("}")] == ".kind { color: var(--muted); font-style: italic; font-size: 15px; "
