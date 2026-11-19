"""podium's line says what the session alive in a project's folder is doing (PLAN.md, "podium shows each
live session in detail", Settled 175; it replaces the one fact of "Whether a session is alive", 6). podium
reads `live`, `live_note` and `runs_in` from conduct status --json; every name here is invented."""

import datetime
import html as markup

import pytest
from test_podium_view import NOW, row

from bernstein import podium

# NOW is 18 October 2026, 09:40:05 UTC
LIVE = {"name": "soups-tools · 18 October", "status": "idle", "kind": "interactive",
        "started": "2026-10-18T07:36:00Z", "pid": 4242, "count": 1, "id": "00000000-0000-4000-8000-000000000000",
        "model": None, "effort": None, "last_reply": "2026-10-18T09:15:00Z"}


def a_row(state="running", duty="mac", **more):
    return dict(dict(row("soups-tools", state, duty=duty), runs_in="code", live=None, live_note=None), **more)


def line(state="running", duty="mac", idle_warn=60, unread=False, **more):
    return podium.row_html(a_row(state, duty, **more), NOW, unread=unread, idle_warn=idle_warn)


def facts(html):
    """The live facts of a line, each as its text."""
    return [part.split(">", 1)[1].split("</li>")[0] for part in html.split('<li class="live')[1:]]


def replied(minutes_ago, **more):
    when = NOW - datetime.timedelta(minutes=minutes_ago, seconds=5)
    return dict(LIVE, last_reply=f"{when:%Y-%m-%dT%H:%M:%SZ}", **more)


# --- as before, where there is nothing to say ---

def test_a_row_from_a_conduct_that_says_nothing_of_live_sessions_is_drawn_as_before():
    old = row("soups-tools", "running", duty="mac")
    assert 'class="live' not in podium.row_html(old, NOW)
    assert line() == podium.row_html(old, NOW)


@pytest.mark.parametrize("state, duty", [("running", "device"), ("stale", "device"), ("off", None),
                                         ("handed-over", None), ("dormant", "device"), ("quiet", "device")])
def test_a_cowork_project_s_line_is_byte_for_byte_as_before_whatever_the_listing(state, duty):
    old = row("soups", state, kind="non-code", duty=duty)
    cowork = dict(old, runs_in="cowork", live=None, live_note=None)
    assert podium.row_html(cowork, NOW) == podium.row_html(old, NOW)
    assert podium.row_html(cowork, NOW, unread=True) == podium.row_html(old, NOW)


def test_a_project_that_is_off_with_no_session_and_no_note_says_nothing_as_the_usual_goes_unsaid():
    assert 'class="live' not in line("off", None)


# --- working or sitting, and for how long ---

def test_a_busy_session_is_working_whenever_it_last_replied():
    assert facts(line(live=replied(300, status="busy")))[0] == "working"
    assert 'class="live long"' not in line(live=replied(300, status="busy"))


def test_an_idle_session_says_how_long_since_its_newest_reply_after_who_is_on_duty():
    html = line(live=LIVE)
    assert ('<ul class="facts"><li>Claude Code, 3 min ago</li><li class="live">idle 25 min</li>'
            '<li class="live">since 07:36 UTC</li><li>opus, high</li></ul>') in html


@pytest.mark.parametrize("minutes, said", [(0, "idle under a minute"), (1, "idle 1 min"), (59, "idle 59 min"),
                                           (60, "idle 1 h"), (125, "idle 2 h 5 min"), (1440, "idle 1 d"),
                                           (4500, "idle 3 d")])
def test_the_idle_time_is_said_in_minutes_hours_or_days(minutes, said):
    assert facts(line(live=replied(minutes), idle_warn=100000))[0] == said


@pytest.mark.parametrize("minutes, level, marked", [(59, 60, False), (60, 60, True), (125, 60, True),
                                                   (25, 10, True), (9, 10, False), (125, 126, False)])
def test_idle_at_or_past_the_level_is_marked_in_words_not_colour_alone(minutes, level, marked):
    html = line(live=replied(minutes), idle_warn=level)
    said = podium.span(minutes)
    if marked:
        assert (f'<li class="live long" title="idle for {level} minutes or more (the setting IDLE_WARN)">'
                f"long idle: {said}</li>") in html
    else:
        assert f'<li class="live">idle {said}</li>' in html and "long idle" not in html


@pytest.mark.parametrize("last", [None, "yesterday", 7, "2026-10-18T10:00:00Z"])
def test_a_reply_time_that_is_not_known_or_is_ahead_of_the_clock_leaves_idle_alone(last):
    assert facts(line(live=dict(LIVE, last_reply=last)))[0] == "idle"


@pytest.mark.parametrize("status, said", [(None, "status not known"), (7, "status not known"),
                                          ("waiting", "waiting"), ("<b>x</b>", "&lt;b&gt;x&lt;/b&gt;")])
def test_a_status_that_is_neither_busy_nor_idle_is_said_as_given_or_as_not_known(status, said):
    assert facts(line(live=dict(LIVE, status=status)))[0] == said


# --- how long it has been alive ---

def test_since_gives_the_time_it_started_with_the_day_when_that_is_not_today():
    assert "since 07:36 UTC" in facts(line(live=LIVE))
    assert "since 22:10 UTC on 17 October 2026" in facts(line(live=dict(LIVE, started="2026-10-17T22:10:00Z",
                                                                       name="soups-tools · 17 October")))


@pytest.mark.parametrize("started", [None, "this morning", 1792051200000])
def test_a_start_that_is_not_known_is_not_said(started):
    assert not [f for f in facts(line(live=dict(LIVE, started=started, name=None))) if f.startswith("since")]


# --- the name, when it is not the one a Start gives ---

def test_the_name_conduct_start_gives_for_the_day_it_started_is_not_said():
    assert not [f for f in facts(line(live=LIVE)) if f.startswith("named")]
    late = dict(LIVE, started="2026-10-17T23:59:59Z", name="soups-tools · 17 October")
    assert not [f for f in facts(line(live=late)) if f.startswith("named")]


@pytest.mark.parametrize("name, said", [
    ("my own name", "named my own name"), ("soups-tools · 17 October", "named soups-tools · 17 October"),
    ("soups · 18 October", "named soups · 18 October"),
    ('<script>alert("x")</script> & é', "named &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; é")])
def test_any_other_name_is_said_as_text(name, said):
    assert said in facts(line(live=dict(LIVE, name=name)))


def test_a_name_is_said_when_the_start_is_not_known_and_no_name_says_nothing():
    assert "named soups-tools · 18 October" in facts(line(live=dict(LIVE, started=None)))
    assert not [f for f in facts(line(live=dict(LIVE, name=None))) if f.startswith("named")]


# --- more than one session in the folder ---

def test_several_sessions_are_said_with_each_name_and_marked():
    html = line(live=dict(LIVE, count=2, names=["first", "soups-tools · 18 October"]))
    assert ('<li class="live several" title="More than one session is alive in this project&#x27;s folder: '
            'archive the ones you do not want, in the app">2 sessions: first, soups-tools · 18 October</li>') in html


@pytest.mark.parametrize("names", [None, "first", [1, 2], ["a", None], []])
def test_several_sessions_whose_names_are_not_given_as_expected_are_counted_only(names):
    found = dict(LIVE, count=3, names=names)
    assert '>3 sessions</li>' in line(live=found)


@pytest.mark.parametrize("count", [1, 0, None, True, "2", -1])
def test_one_session_or_a_count_that_is_not_a_number_says_nothing_of_several(count):
    assert 'class="live several"' not in line(live=dict(LIVE, count=count, names=["a", "b"]))


def test_names_of_several_are_text_never_markup():
    html = line(live=dict(LIVE, count=2, names=["<i>a</i>", 'b"c']))
    assert ">2 sessions: &lt;i&gt;a&lt;/i&gt;, b&quot;c</li>" in html and "<i>" not in html


# --- the model and effort in use ---

LOWER = ' title="lower than the project asks for (opus, high)"'


@pytest.mark.parametrize("model, effort, said, lower", [
    ("claude-opus-4-8", "high", None, False),                                   # as asked
    ("claude-opus-4-8", None, None, False),
    (None, "high", None, False),
    (None, None, None, False),
    ("claude-fable-5-2", "high", "in use: claude-fable-5-2, high", False),      # higher
    ("claude-fable-5-2", None, "in use: claude-fable-5-2", False),
    ("claude-sonnet-5-5", "high", "in use: claude-sonnet-5-5, high (lower than asked)", True),
    ("claude-haiku-5-5", None, "in use: claude-haiku-5-5 (lower than asked)", True),
    ("claude-opus-4-8", "medium", "in use: claude-opus-4-8, medium (lower than asked)", True),
    ("claude-opus-4-8", "max", "in use: claude-opus-4-8, max", False),
    ("claude-fable-5-2", "low", "in use: claude-fable-5-2, low (lower than asked)", True),
    ("claude-sonnet-5-5", "max", "in use: claude-sonnet-5-5, max (lower than asked)", True),
    (None, "medium", "in use: effort medium (lower than asked)", True),
    (None, "xhigh", "in use: effort xhigh", False),
    ("invented-model", "high", "in use: invented-model, high", False),         # none of the four words: not marked
    ("claude-opus-4-8", "turbo", "in use: claude-opus-4-8, turbo", False),      # an effort that is not one of the five
    ("CLAUDE-OPUS-4-8", "HIGH", None, False),
])
def test_the_model_and_effort_in_use_are_said_when_they_differ_and_marked_when_lower(model, effort, said, lower):
    html = line(live=dict(LIVE, model=model, effort=effort))
    shown = [f for f in facts(html) if f.startswith("in use")]
    assert shown == ([said] if said else [])
    assert (f'<li class="live lower"{LOWER}>' in html) == lower
    if said:
        assert html.index("in use") > html.index("<li>opus, high</li>")     # beside what the project asks for


def test_a_project_that_asks_for_a_model_by_its_id_is_compared_by_the_word_in_it_or_as_text():
    asks = dict(a_row(), model="claude-opus-4-8", effort="high")
    same = podium.row_html(dict(asks, live=dict(LIVE, model="claude-opus-4-9")), NOW)
    assert "in use" not in same
    odd = dict(a_row(), model="invented-model", effort="high")
    assert "in use" not in podium.row_html(dict(odd, live=dict(LIVE, model="invented-model")), NOW)
    assert "in use: another-model" in podium.row_html(dict(odd, live=dict(LIVE, model="another-model")), NOW)


def test_a_model_in_use_is_text_never_markup():
    html = line(live=dict(LIVE, model='<img src=x onerror="a()">', effort="<b>"))
    assert "in use: &lt;img src=x onerror=&quot;a()&quot;&gt;, &lt;b&gt;</li>" in html and "<img" not in html


# --- the badge's words where the duty and the listing disagree ---

@pytest.mark.parametrize("state, duty, note, alive, words, tone, hint", [
    ("stale", "mac", "alive, not watching mail", True, "alive, not watching mail", "warn",
     "speak to it in the app"),
    ("dormant", "mac", "alive, not watching mail", True, "dormant, not watching mail", "warn",
     "speak to it in the app"),
    ("stale", "mac", "alive, not watching mail; 2 sessions alive in its folder", True,
     "alive, not watching mail", "warn", "speak to it in the app"),
    ("stale", "mac", "no session alive: it ended without a handover", False, "ended without a handover", "alert",
     "conduct reset soups-tools"),
    ("dormant", "mac", "no session alive: it ended without a handover", False, "ended without a handover", "alert",
     "conduct reset soups-tools"),
    ("handed-over", None, "alive after its handover: not archived", True,
     "alive after its handover: not archived", "warn", "archive it in the app"),
    ("off", None, "alive, not on duty", True, "alive, not on duty", "warn", "it may be starting"),
    ("running", "mac", "no session alive, though its duty is fresh: a watch has outlived its session", False,
     "a watch with no session", "alert", "a watch has outlived its session"),
])
def test_the_badge_says_the_disagreement_with_what_to_do_on_hover(state, duty, note, alive, words, tone, hint):
    html = line(state, duty, live=LIVE if alive else None, live_note=note)
    start = html.index('<span class="badge ')
    badge = html[start:html.index("</span>", start)]
    assert badge.startswith(f'<span class="badge {tone}" title="') and badge.endswith(f'">{words}')
    assert hint in badge
    assert podium.badge(a_row(state, duty, live=LIVE if alive else None, live_note=note), NOW) == (words, tone)


def test_the_disagreement_takes_the_badge_from_a_status_the_session_reported():
    dreaming = {"status": "dreaming", "set": "2026-10-18T09:20:00Z", "until": "2026-10-18T10:20:00Z"}
    gone = "no session alive, though its duty is fresh: a watch has outlived its session"
    assert podium.badge(a_row(reported=dreaming, live_note=gone), NOW) == ("a watch with no session", "alert")
    assert podium.badge(a_row(reported=dreaming, live=LIVE), NOW) == ("dreaming until 10:20 UTC", "busy")


@pytest.mark.parametrize("note", ["2 sessions alive in its folder", None])
def test_with_no_disagreement_the_badge_is_the_state_s_with_no_hover(note):
    html = line(live=dict(LIVE, count=2, names=["a", "b"]), live_note=note)
    assert '<span class="badge ok">running</span>' in html


def test_a_note_podium_does_not_know_is_said_as_it_is_among_the_facts_and_the_badge_is_the_state_s():
    html = line("stale", live=LIVE, live_note="<i>something new</i>; 2 sessions alive in its folder")
    assert '<span class="badge alert">stale</span>' in html
    assert facts(html)[0] == "&lt;i&gt;something new&lt;/i&gt;; 2 sessions alive in its folder"
    alone = line("stale", live=None, live_note="something new")
    assert facts(alone) == ["something new"]


def test_a_label_on_a_card_says_the_same_words_as_the_line_s_badge():
    gone = a_row("stale", live_note="no session alive: it ended without a handover")
    assert '<span class="badge alert">ended without a handover</span>' in podium.label_html(gone, "claw", NOW)


# --- the listing could not be read ---

def test_with_the_listing_unread_a_project_on_the_mac_says_the_live_state_is_not_known():
    html = line("stale", unread=True)
    assert facts(html) == ["live state not known"]
    assert '<li class="live unknown">live state not known</li>' in html
    assert '<span class="badge alert">stale</span>' in html


def test_with_the_listing_unread_a_row_that_does_not_say_where_it_runs_is_as_before():
    old = row("soups-tools", "stale", duty="mac")
    assert podium.row_html(old, NOW, unread=True) == podium.row_html(old, NOW)
    assert podium.row_html(dict(old, runs_in=None), NOW, unread=True) == podium.row_html(old, NOW)


# --- what conduct gives in another shape ---

@pytest.mark.parametrize("found, note", [("alive", None), (["a"], None), (7, None), (None, 7), (None, ["x"]),
                                         (True, {"a": 1})])
def test_live_and_a_note_that_are_not_the_shape_conduct_gives_say_nothing(found, note):
    html = line(live=found, live_note=note)
    assert 'class="live' not in html and '<span class="badge ok">running</span>' in html


def test_an_empty_live_says_only_that_its_status_is_not_known():
    assert facts(line(live={})) == ["status not known"]


# --- the buttons follow the real state ---

def note_of(html, verb):
    start = html.index(f'data-verb="{verb}"')
    button = html[start:html.index(">", start)]
    return markup.unescape(button.split('data-note="', 1)[1].split('"', 1)[0]) if "data-note" in button else None


SECOND = ("A session is already alive in this project's folder (soups-tools · 18 October, idle): a Start would "
          "open a second one. Speak to that session in the app, or archive it there, first.")


@pytest.mark.parametrize("state, note", [("off", "alive, not on duty"),
                                         ("handed-over", "alive after its handover: not archived")])
def test_start_says_first_that_a_session_is_already_alive_in_the_folder(state, note):
    html = line(state, None, live=LIVE, live_note=note)
    assert note_of(html, "start") == SECOND
    assert f'title="{markup.escape(SECOND, quote=True)}"' in html


def test_start_with_no_session_alive_is_offered_plainly():
    assert note_of(line("off", None), "start") is None
    assert note_of(line("handed-over", None), "start") is None


def test_start_names_the_session_as_text_and_says_what_is_not_known():
    html = line("off", None, live=dict(LIVE, name='a "b" <c>', status=None), live_note="alive, not on duty")
    assert '(a "b" <c>, status not known)' in note_of(html, "start")
    assert "<c>" not in html and "(a &quot;b&quot; &lt;c&gt;, status not known)" in html
    assert "(a session with no name, idle)" in note_of(line("off", None, live=dict(LIVE, name=None)), "start")


def test_wake_of_a_session_alive_and_not_watching_says_it_reads_the_wake_when_he_next_types():
    html = line("stale", live=LIVE, live_note="alive, not watching mail")
    assert note_of(html, "wake") == ("Its session is alive (soups-tools · 18 October, idle) but not watching mail: "
                                     "it reads the Wake only when you next type to it.")


def test_wake_where_no_session_is_alive_says_nothing_would_read_it():
    html = line("stale", live_note="no session alive: it ended without a handover")
    assert note_of(html, "wake") == ("No session is alive in this project's folder, so nothing would read a Wake: "
                                     "conduct reset soups-tools clears its duty, and Start then starts it afresh.")


def test_wake_with_nothing_known_of_a_live_session_keeps_its_words():
    assert note_of(line("stale"), "wake") == podium.WAKE_WAITS
    assert note_of(line("dormant", live=LIVE), "wake") is None      # its duty is fresh: its quiet watch is running


def all_note(rows, verb):
    html = podium.view(rows, NOW)
    start = html.index(f'data-verb="{verb}" data-all="1"')
    button = html[start:html.index(">", start)]
    return button.split('data-note="', 1)[1].split('"', 1)[0] if "data-note" in button else None


def test_stop_dormant_and_dream_for_all_say_which_sessions_are_alive_and_will_be_sent_nothing():
    rows = [a_row(), dict(a_row("stale", live=LIVE, live_note="alive, not watching mail"), mailbox="stews-tools"),
            dict(a_row("dormant", live=LIVE, live_note="alive, not watching mail"), mailbox="pies-tools",
                 duty=dict(a_row("stale")["duty"], stale=True))]
    said = ("stews-tools and pies-tools are alive but not watching mail: conduct passes a stale duty over and sends "
            "them nothing. Speak to them in the app.")
    for verb in ("stop", "dormant", "dream"):
        assert all_note(rows, verb) == said
    one = ("stews-tools is alive but not watching mail: conduct passes a stale duty over and sends it nothing. "
           "Speak to it in the app.")
    assert all_note(rows[:2], "stop") == one


def test_the_all_buttons_say_nothing_more_when_every_session_alive_is_watching():
    rows = [a_row(live=LIVE), dict(a_row("stale"), mailbox="stews-tools")]
    for verb in ("stop", "dormant", "dream"):
        assert all_note(rows, verb) is None


# --- the page passes the level and whether the listing was read to each line ---

def test_the_view_marks_idle_by_the_level_it_is_given_and_says_not_known_when_the_listing_was_not_read():
    rows = [a_row(live=replied(30))]
    assert "long idle: 30 min" in podium.view(rows, NOW, idle_warn=30)
    assert "long idle" not in podium.view(rows, NOW)
    unread = {"live_listing": {"read": False, "why": "claude was not found"}}
    assert "live state not known" in podium.view([a_row("stale")], NOW, top=unread)
    for top in (None, {}, {"live_listing": {"read": True, "why": None}}, {"live_listing": "odd"}, {"live_listing": None}):
        assert "live state not known" not in podium.view([a_row("stale")], NOW, top=top)


def test_a_button_s_note_is_said_first_in_its_dialog_before_the_options():
    page = podium.page("")
    assert page.index('<p id="act-waits" class="note" hidden></p>') < page.index('<div id="act-options"></div>')
    assert page.index('<h2 id="act-title"></h2>') < page.index('<p id="act-waits"')


def test_a_sentence_podium_has_a_badge_for_is_not_said_again_among_the_facts():
    html = line("stale", live=LIVE, live_note="alive, not watching mail; 2 sessions alive in its folder")
    assert facts(html)[0] == "idle 25 min"
    assert html.count("not watching mail") == 3     # the badge, and the Wake button's note and hover
    assert facts(line("stale", live_note="no session alive: it ended without a handover")) == []


def test_an_effort_is_ranked_as_a_whole_word_so_high_in_use_is_lower_than_xhigh_asked():
    asks = dict(a_row(), effort="xhigh")
    html = podium.row_html(dict(asks, live=dict(LIVE, model="claude-opus-4-8", effort="high")), NOW)
    assert ('<li class="live lower" title="lower than the project asks for (opus, xhigh)">'
            "in use: claude-opus-4-8, high (lower than asked)</li>") in html

