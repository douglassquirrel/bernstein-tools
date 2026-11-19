"""podium: a control panel for lobster sessions, a local web page that only ever calls conduct.

PLAN.md ("The control panel, podium") is the specification. It serves on 127.0.0.1 only, only while
its Terminal command runs, and every request needs the token in the link it prints. Exit codes: 0
stopped, 2 bad arguments or settings, 4 it could not start serving.
"""

import argparse
import datetime
import errno
import hmac
import html
import http.server
import json
import os
import re
import secrets
import shlex
import subprocess
import tempfile
import threading
import urllib.parse

from bernstein.conduct import day
from bernstein.conduct import session_name as started_name
from bernstein.settings import EFFORTS, SettingsRefused, check_port, read_settings

TONES = {"running": "ok", "dormant": "sleep", "quiet": "warn", "stale": "alert", "handed-over": "off", "off": "off"}


def ago(minutes):
    """How long ago a session last checked in, from the listing's whole minutes."""
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0:
        return "at an unknown time"
    if minutes == 0:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 1440:
        hours, rest = divmod(minutes, 60)
        return f"{hours} h {rest} min ago" if rest else f"{hours} h ago"
    return f"{minutes // 1440} d ago"


def stamp(text):
    """lobster-mail's UTC stamp as a time, or None when the text is not one."""
    try:
        when = datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None
    return when.replace(tzinfo=datetime.timezone.utc)


def clock(when, now):
    """A time of day in UTC, with the day when it is not today's."""
    text = f"{when:%H:%M} UTC"
    return text if when.date() == now.date() else f"{text} on {day(when)}"


# Where the duty and the listing of live sessions disagree, conduct's sentence (live_note) becomes the
# badge: (conduct's sentence, the badge's words, its tone, what he can do, said on hover).
LIVE_BADGES = (
    ("no session alive, though its duty is fresh: a watch has outlived its session", "a watch with no session",
     "alert", ("Its duty is fresh but no session is alive in its folder: a watch has outlived its session, or the "
               "session was opened in another folder.")),
    ("no session alive: it ended without a handover", "ended without a handover", "alert",
     "No session is alive in its folder: conduct reset {name} clears its duty, and Start then starts it afresh."),
    ("alive, not watching mail", "alive, not watching mail", "warn",
     ("Its session is alive but its mail watch has stopped: it reads mail only when you next type to it, so "
      "speak to it in the app.")),
    ("alive after its handover: not archived", "alive after its handover: not archived", "warn",
     "It has handed over and its session is still open: archive it in the app."),
    ("alive, not on duty", "alive, not on duty", "warn",
     ("A session is alive in its folder and has not taken the duty: it may be starting. If it is not, speak to "
      "it in the app.")),
)
SEVERAL = re.compile(r"[0-9]+ sessions alive in its folder")


def live_note(row):
    """conduct's sentence for the row, in its parts, or [] when it gives none."""
    note = row.get("live_note")
    return note.split("; ") if isinstance(note, str) else []


def live_badge(row):
    """(words, tone, what to do) where conduct says the duty and the listing of live sessions disagree, in
    a sentence podium knows; None otherwise. podium works none of it out: it words what conduct says."""
    for part in live_note(row):
        for sentence, words, tone, hint in LIVE_BADGES:
            if part == sentence:
                if sentence == "alive, not watching mail" and row.get("state") == "dormant":
                    words = "dormant, not watching mail"
                return words, tone, hint.replace("{name}", str(row["mailbox"]))
    return None


def badge(row, now):
    """(words, tone) for a row's state. Where the duty and the listing of live sessions disagree, that is
    the badge. Otherwise a running session's own report takes it, until its finish time passes: after that
    it is overdue, not trusted."""
    disagreement = live_badge(row)
    if disagreement:
        return disagreement[0], disagreement[1]
    state = row["state"]
    said = row.get("reported")
    if state != "running" or not said:
        return state.replace("-", " "), TONES.get(state, "off")
    status = str(said.get("status", ""))
    until = said.get("until")
    if not until:
        return status, "busy"
    when = stamp(until)
    if when is None:
        return f"{status} until {until}", "busy"
    if when < now:
        return f"{status}, overdue since {clock(when, now)}", "warn"
    return f"{status} until {clock(when, now)}", "busy"


def joined(names):
    """Names as a sentence says them: "a", "a and b", "a, b and c"."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def groups(rows):
    """The rows as the page lays them out, each mailbox on one full line only: a card per non-code project
    with, under it, its home claw when no other non-code project names that one and any claw that has no
    mailbox, and a label for each other project it names; then "Claws", by name: every other tools project,
    saying who uses it; then mailboxes whose project cannot be read, then bernstein's own, then a card per
    conductor with its claw under it."""
    by_name = {r["mailbox"]: r for r in rows}
    ganglia = [r for r in rows if r["kind"] == "non-code"]

    def users(name):
        return [g["mailbox"] for g in ganglia if name in g["claws"]]

    cards, claws, unstartable, conductors, bernstein, on_a_card = [], [], [], [], None, set()
    for r in rows:
        if r["kind"] == "conductor":
            conductors.append((r, [(by_name.get(name, {"mailbox": name, "missing": True}), "claw")
                                   for name in r["claws"]]))
        elif r["mailbox"] == "bernstein":
            bernstein = r
        elif r["kind"] == "non-code":
            full, labels = [], []
            for name in r["claws"]:
                what = "home claw" if name == r["sister"] else "claw"
                found = by_name.get(name)
                if found is None:
                    full.append(({"mailbox": name, "missing": True}, what))
                elif what == "home claw" and found["kind"] == "code" and found["serves"] == [r["mailbox"]]:
                    full.append((found, what))
                    on_a_card.add(name)
                else:
                    labels.append((found, what))
            cards.append((r, full, labels))
        elif r["kind"] is None:
            unstartable.append(r)
    served_by_a_conductor = {name for r in rows if r["kind"] == "conductor" for name in r["claws"]}
    for r in sorted(rows, key=lambda r: r["mailbox"]):
        if (r["kind"] in (None, "non-code", "conductor") or r["mailbox"] == "bernstein"
                or r["mailbox"] in on_a_card or r["mailbox"] in served_by_a_conductor):
            continue
        homes = [g["mailbox"] for g in ganglia if r["mailbox"] in g["claws"] and g["sister"] == r["mailbox"]]
        others = [name for name in users(r["mailbox"]) if name not in homes]
        said = ", ".join(([f"home claw of {joined(homes)}"] if homes else [])
                         + ([f"used by {joined(others)}"] if others else []))
        claws.append((r, said or r["kind"]))
    return {"cards": cards, "claws": claws, "unstartable": unstartable, "bernstein": bernstein,
            "conductors": conductors}


SESSIONS = {"mac": "Claude Code", "device": "Claude Cowork"}


def session_name(holder):
    """The duty's holder as the page says it: lobster-mail's two usual session names are the two ways a session
    runs (`mac`: Claude Code on the Mac; `device`: a Claude Cowork session, in the app's virtual machine)."""
    return SESSIONS.get(holder, str(holder))


LABELS = {"start": "Start", "stop": "Stop", "dormant": "Dormant", "dream": "Dream", "wake": "Wake"}
ASLEEP = ("dormant", "quiet", "stale")


def buttons(row):
    """The verbs a row offers, from its state. conduct still decides when one is pressed."""
    if row["mailbox"] == "bernstein" or row.get("missing") or row.get("kind") == "conductor":
        return []           # conduct has nothing to do to the session that runs it
    state = row["state"]
    if state == "running":
        return ["stop", "dormant", "dream"]
    if state in ASLEEP:
        return ["wake"]
    return ["start"] if row["kind"] is not None and not row["refused"] else []


WAKE_WAITS = ("This session is not watching mail (a Claude Cowork session, or one whose watch has stopped): it wakes "
              "when you next type to it.")
SOME_WAKES_WAIT = ("Some of these sessions are not watching mail (a Claude Cowork session, or one whose watch has "
                   "stopped): each of those wakes when you next type to it.")


def watching(row):
    """Whether a session that is asleep will be given a turn by a Wake: only a Claude Code session on the Mac
    whose duty is fresh, which is what its quiet watch keeps it. Any other reads the Wake at its next turn."""
    duty = row.get("duty")
    return isinstance(duty, dict) and duty.get("holder") == "mac" and not duty.get("stale")


def noted(note):
    """A button's note, for its hover and for the dialog it opens."""
    return f' data-note="{e(note)}" title="{e(note)}"' if note else ""


def buttons_for_all(rows):
    """The verbs offered for every session at once: bernstein's own and a conductor's are never among them."""
    states = {r["state"] for r in rows if r["mailbox"] != "bernstein" and r["kind"] != "conductor"}
    return (["stop", "dormant", "dream"] if "running" in states else []) + (
        ["wake"] if states.intersection(ASLEEP) else [])


OPEN_LINK = re.compile(r"claude://claude\.ai/(epitaxy/local_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                       r"|cowork/session_[A-Za-z0-9]{8,64})")


def open_link(row, now):
    """A link that opens the project's newest session in the desktop app, when conduct found one. Only the
    app's own kind of link is ever put on the page, whatever the listing says."""
    found = row.get("session")
    link = found.get("link") if isinstance(found, dict) else None
    if not isinstance(link, str) or not OPEN_LINK.fullmatch(link):
        return ""
    when = stamp(found.get("last_activity"))
    title = "Open its newest session in the Claude app" + (f" (last active {clock(when, now)})" if when else "")
    return f'<a class="open" href="{e(link)}" title="{e(title)}">Open</a>'


def e(text):
    """Anything from outside, as text for the page: never markup."""
    return html.escape(str(text), quote=True)


def count(value):
    """A whole number that is not negative, and not true or false."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def context_item(row, now):
    """How full the context window of the row's session is, as one of the row's facts: a small bar that
    fills with the percentage and the bare figure beside it, with the detail in the title. Nothing for a
    row with no session; "context not known", and no bar, when conduct could not tell or when what it says
    is not the shape it gives. The mark at the warning level is conduct's to give (warn), never worked out
    here. The bar is never longer than its outline; the figure says the real percentage."""
    if not isinstance(row.get("session"), dict):
        return ""
    found = row.get("context")
    if not (isinstance(found, dict) and count(found.get("percent")) and count(found.get("tokens"))
            and count(found.get("window")) and found["window"] > 0 and isinstance(found.get("warn"), bool)):
        return '<li class="context unknown">context not known</li>'
    when = stamp(found.get("as_of"))
    said = f"{found['percent']}% of context"
    title = (f"{said}: {found['tokens']:,} tokens in use" + (f" at {clock(when, now)}" if when else "")
             + f", of a window of {found['window']:,} (the setting CONTEXT_WINDOW)")
    if found["warn"]:
        title += "; at or over the warning level (the setting CONTEXT_WARN)"
    marked = "context warn" if found["warn"] else "context"
    # the figure beside the bar is for the eye; a screen reader is told once, by the bar's label
    return (f'<li class="{marked}" title="{e(title)}"><svg class="bar" viewBox="0 0 100 8" '
            f'preserveAspectRatio="none" role="img" aria-label="{e(said)}"><rect class="fill" '
            f'width="{min(found["percent"], 100)}" height="8"/></svg>'
            f'<span aria-hidden="true">{found["percent"]}%</span></li>')


def span(minutes):
    """A length of time in whole minutes, as the page says it."""
    if minutes == 0:
        return "under a minute"
    return ago(minutes)[: -len(" ago")]


def alive(row):
    """The session conduct says is alive in the row's folder, or None."""
    return row.get("live") if isinstance(row.get("live"), dict) else None


def named(found):
    """A live session in a sentence: its name and its status, or what is not known of them."""
    name = found.get("name") if isinstance(found.get("name"), str) else "a session with no name"
    status = found.get("status") if isinstance(found.get("status"), str) else "status not known"
    return f"{name}, {status}"


def live_items(row, now, idle_warn=60, unread=False):
    """What the session alive in the row's folder is doing, as facts of the row, from conduct's `live`:
    working, or idle and for how long since its newest reply (marked "long idle" at or past idle_warn
    minutes); since when it has been alive; its name, when it is not the one conduct start gives for that
    day; and how many sessions are there, when more than one. Before them, a sentence of conduct's that
    podium has no badge for. With the listing unread, a project that runs on the Mac says the live state
    is not known, so that a blank is never read as "not alive". Nothing for any other row."""
    items = []
    known = {sentence for sentence, _words, _tone, _hint in LIVE_BADGES}
    if any(part not in known and not SEVERAL.fullmatch(part) for part in live_note(row)):
        items.append(f'<li class="live">{e(row["live_note"])}</li>')
    found = alive(row)
    if found is None:
        if unread and row.get("runs_in") == "code":
            items.append('<li class="live unknown">live state not known</li>')
        return items
    status = found.get("status")
    if status == "busy":
        items.append('<li class="live">working</li>')
    elif status == "idle":
        replied = stamp(found.get("last_reply"))
        minutes = int((now - replied).total_seconds() // 60) if replied and replied <= now else None
        if minutes is None:
            items.append('<li class="live">idle</li>')
        elif minutes >= idle_warn:
            items.append(f'<li class="live long" title="idle for {idle_warn} minutes or more (the setting '
                         f'IDLE_WARN)">long idle: {span(minutes)}</li>')
        else:
            items.append(f'<li class="live">idle {span(minutes)}</li>')
    else:
        items.append(f'<li class="live">{e(status) if isinstance(status, str) else "status not known"}</li>')
    began = stamp(found.get("started"))
    if began:
        items.append(f'<li class="live">since {clock(began, now)}</li>')
    name = found.get("name")
    if isinstance(name, str) and (began is None or name != started_name(row["mailbox"], began)):
        items.append(f'<li class="live">named {e(name)}</li>')
    if count(found.get("count")) and found["count"] > 1:
        names = found.get("names")
        each = ": " + ", ".join(names) if isinstance(names, list) and names and all(
            isinstance(n, str) for n in names) else ""
        items.append('<li class="live several" title="More than one session is alive in this project&#x27;s '
                     f'folder: archive the ones you do not want, in the app">{found["count"]} sessions{e(each)}</li>')
    return items


MODELS = ("haiku", "sonnet", "opus", "fable")       # lowest first, by the word in the model's id


def rank(text, order):
    """Where a model's id or an effort stands in its order, lowest first; None when it names none of them."""
    found = [at for at, word in enumerate(order) if word in text.lower()] if order is MODELS else [
        at for at, word in enumerate(order) if word == text.lower()]
    return found[0] if found else None


def in_use_item(row):
    """The model and effort the live session is really running on, beside what the project asks for: said
    only when one of them differs, and marked "lower than asked" when it is the lower. A model whose id has
    none of the four words is shown and never marked."""
    found = alive(row)
    asked_model, asked_effort = row.get("model"), row.get("effort")
    if found is None or not isinstance(asked_model, str) or not isinstance(asked_effort, str):
        return ""
    model = found.get("model") if isinstance(found.get("model"), str) else None
    effort = found.get("effort") if isinstance(found.get("effort"), str) else None
    model_ranks = (rank(model, MODELS), rank(asked_model, MODELS)) if model else (None, None)
    effort_ranks = (rank(effort, EFFORTS), rank(asked_effort, EFFORTS)) if effort else (None, None)
    same_model = model is None or model.lower() == asked_model.lower() or (
        None not in model_ranks and model_ranks[0] == model_ranks[1])
    same_effort = effort is None or effort.lower() == asked_effort.lower()
    if same_model and same_effort:
        return ""
    lower = any(None not in ranks and ranks[0] < ranks[1] for ranks in (model_ranks, effort_ranks))
    said = "in use: " + (", ".join(part for part in (model, effort) if part) if model else f"effort {effort}")
    if not lower:
        return f'<li class="live">{e(said)}</li>'
    return (f'<li class="live lower" title="lower than the project asks for ({e(asked_model)}, {e(asked_effort)})">'
            f"{e(said)} (lower than asked)</li>")


def button_note(row, verb):
    """What a button says on hover and in its dialog, from what is really alive: a Start where a session is
    already alive in the folder with nobody on duty, and a Wake for a session that is not watching mail."""
    found = alive(row)
    if verb == "start" and found is not None and not row.get("duty"):
        return (f"A session is already alive in this project's folder ({named(found)}): a Start would open a "
                "second one. Speak to that session in the app, or archive it there, first.")
    if verb == "wake" and not watching(row):
        if found is not None:
            return (f"Its session is alive ({named(found)}) but not watching mail: it reads the Wake only when "
                    "you next type to it.")
        if any(part.startswith("no session alive") for part in live_note(row)):
            return ("No session is alive in this project's folder, so nothing would read a Wake: conduct reset "
                    f"{row['mailbox']} clears its duty, and Start then starts it afresh.")
        return WAKE_WAITS
    return ""


def label_html(row, what, now):
    """A project a card names but does not draw in full: its name, what it is to the card and its state, in the
    words and tone of its own badge, as a link to its one full line on the page. A screen reader is told the
    three as the link's name."""
    words, tone = badge(row, now)
    return (f'<a class="label" href="#claw-{e(row["mailbox"])}" aria-label="{e(row["mailbox"])}, {e(what)}, '
            f'{e(words)}">{e(row["mailbox"])} <span class="kind">{e(what)}</span> '
            f'<span class="badge {tone}">{e(words)}</span></a>')


def labels_html(labels, now):
    """A card's row of labels; nothing when it has none."""
    if not labels:
        return ""
    return '<div class="labels">' + "".join(label_html(r, what, now) for r, what in labels) + "</div>"


CHECK_MINUTES = 10      # how long a new session is waited for after a Start
LINE_MINUTES = 30       # how long "no session has appeared" stays on the project's line
STARTED = {"right": "started right", "waiting": "started", "wrong": "started wrong", "none": "started wrong"}


def start_checks(starts, rows, top, now):
    """What became of each Start podium sent and remembers, from what conduct status --json says is alive:
    one check for each that can be checked, in the order they were sent. starts is {project: {"at": when
    the Start was sent, "entry": its place in what podium has run, "right": what was said once a new
    session was seen in the project's folder}}; a Start seen to be right is marked so in it, and stays so.

    A check is {"project", "entry", "state", "said", "line"}: state is right (a session that started
    after the Start is alive in the project's folder), wrong (one is alive in a folder that is no listed
    mailbox's, and none in the project's), waiting (neither, in the first CHECK_MINUTES) or none (neither,
    after them); line says whether the project's line says it too. Nothing is checked when conduct did not
    read the listing of live sessions, nor for a project that is not listed or does not run on the Mac."""
    listing = top.get("live_listing") if isinstance(top, dict) else None
    if not isinstance(listing, dict) or listing.get("read") is not True:
        return []
    by_name = {r["mailbox"]: r for r in rows}
    found = []
    for project, start in sorted(starts.items(), key=lambda item: item[1]["entry"]):
        row = by_name.get(project)
        if row is None or row.get("runs_in") != "code":
            continue
        age = now - start["at"]
        here = alive(row)
        began = stamp(here.get("started")) if here else None
        if start["right"] is None and began is not None and began >= start["at"]:
            name = here.get("name") if isinstance(here.get("name"), str) else "a session with no name"
            on = ", ".join(here[key] for key in ("model", "effort") if isinstance(here.get(key), str)
                           and (key == "model" or isinstance(here.get("model"), str)))
            start["right"] = f"Started, in the right folder: {name}." + (f" It is running on {on}." if on else "")
        if start["right"] is not None:
            found.append({"project": project, "entry": start["entry"], "state": "right", "said": start["right"],
                          "line": age <= datetime.timedelta(minutes=CHECK_MINUTES)})
            continue
        strays = []
        for session in top.get("live_elsewhere") or []:
            if not isinstance(session, dict) or not isinstance(session.get("folder"), str):
                continue
            opened = stamp(session.get("started"))
            if opened is not None and opened >= start["at"] and session["folder"] not in strays:
                strays.append(session["folder"])
        if strays:
            found.append({"project": project, "entry": start["entry"], "state": "wrong", "line": True,
                          "said": (f"A session that started after this Start is alive in {joined(strays)}, which "
                                   "is no project's folder, and none is in this project's folder: it may have "
                                   "opened in the wrong folder. If so, stop that session in the app, press Start "
                                   "again, and before you send the first line change the form's folder to another "
                                   "and back.")})
        elif age <= datetime.timedelta(minutes=CHECK_MINUTES):
            found.append({"project": project, "entry": start["entry"], "state": "waiting", "line": True,
                          "said": "No new session in this project's folder yet: in the app, confirm the folder "
                                  "and send the first line."})
        else:
            found.append({"project": project, "entry": start["entry"], "state": "none",
                          "said": "No session has appeared: was the first line sent?",
                          "line": age <= datetime.timedelta(minutes=LINE_MINUTES)})
    open_still = [c["project"] for c in found if c["state"] != "right"]
    for c in found:
        others = [name for name in open_still if name != c["project"]]
        if c["state"] == "wrong" and others:
            c["said"] += f" A Start of {joined(others)} is waited for too: it may be that one's."
    return found


def check_html(found):
    """A check as a paragraph, for the project's line and for the Start's run in the Activity."""
    return f'<p class="{STARTED[found["state"]]}">{e(found["said"])}</p>'


def row_html(row, now, label=None, claw=False, anchor=False, unread=False, idle_warn=60, check=None):
    """One mailbox's line on the page. label is what the row is to the card it sits in; anchor, whether a
    label elsewhere on the page points to it; unread, whether conduct could not read the listing of live
    sessions; idle_warn, the minutes at which an idle session is marked; check, what became of the Start
    podium last sent it, when the line is to say so."""
    mark = f' id="claw-{e(row["mailbox"])}"' if anchor else ""
    start = f'<div class="row claw"{mark}>' if claw else f'<div class="row"{mark}>'
    kind = label or row.get("kind")
    who = f'<div class="who"><span class="name">{e(row["mailbox"])}</span>'
    who += f' <span class="kind">{e(kind)}</span></div>' if kind else "</div>"
    if row.get("missing"):
        return f'{start}{who}<span class="badge off">no mailbox</span></div>'
    words, tone = badge(row, now)
    duty = row.get("duty")
    facts = []      # only what is not the usual: nobody on duty, normal pace and no mail go unsaid
    if duty:
        facts.append(f"<li>{e(session_name(duty.get('holder')))}, {ago(duty.get('minutes'))}</li>")
    facts.extend(live_items(row, now, idle_warn, unread))
    if row["pace"] != "normal":
        facts.append(f"<li>pace {e(row['pace'])}</li>")
    if row["new"]:
        facts.append(f'<li class="new">{e(row["new"])} new</li>')
    if row["open"]:
        facts.append(f"<li>{e(row['open'])} open</li>")
    if row.get("model"):
        facts.append(f"<li>{e(row['model'])}, {e(row['effort'])}</li>")
    if in_use_item(row):
        facts.append(in_use_item(row))
    if context_item(row, now):
        facts.append(context_item(row, now))
    said = row.get("reported")
    if said and row["state"] != "running":
        facts.append("<li>reporting " + e('"' + str(said.get("status", "")) + '"') + "</li>")
    facts = f'<ul class="facts">{"".join(facts)}</ul>' if facts else ""
    refused = ""
    if row.get("refused") and row["mailbox"] != "bernstein":   # conduct never starts bernstein's own session
        refused = f'<p class="refused">Cannot start: {e(row["refused"])}</p>'
    acts = open_link(row, now) + "".join(
        f'<button type="button" class="act" data-verb="{verb}" data-project="{e(row["mailbox"])}"'
        f'{noted(button_note(row, verb))}>'
        f"{LABELS[verb]}</button>" for verb in buttons(row))
    acts = f'<div class="acts">{acts}</div>' if acts else ""
    disagreement = live_badge(row)
    hint = f' title="{e(disagreement[2])}"' if disagreement else ""
    return (f'{start}{who}<span class="badge {tone}"{hint}>{e(words)}</span>'
            f"{facts}{acts}{refused}{check_html(check) if check else ''}</div>")


def activity(entries, checks=()):
    """What podium has run since it started, newest first; nothing when it has run nothing. A Start that
    was checked says, under its reminder, what became of it."""
    if not entries:
        return ""
    checked = {found["entry"]: found for found in checks}
    runs = []
    for index, entry in reversed(list(enumerate(entries))):
        done = entry["exit"] is not None
        mark = f'exit {e(entry["exit"])}' if done else "not run"
        tone = "ok" if entry["exit"] == 0 else "alert"
        when = stamp(entry["time"])
        time = f"{when:%H:%M:%S} UTC" if when else e(entry["time"])
        trouble = f'<p class="refused">{e(entry["log_error"])}</p>' if entry.get("log_error") else ""
        # a Start that worked closes its box, so what only he can do in the app is said here
        remind = f'<p class="remind">{e(entry["reminder"])}</p>' if entry.get("reminder") else ""
        remind += check_html(checked[index]) if index in checked else ""
        runs.append(f'<div class="run"><p class="what"><span class="time">{time}</span> '
                    f'<code>{e(entry["command"])}</code> <span class="badge {tone}">{mark}</span></p>'
                    f'<pre>{e(entry["output"])}{e(entry["error"])}</pre>{remind}{trouble}</div>')
    return '<h2>Activity</h2><section class="card log">' + "".join(runs) + "</section>"


def view(rows, now, error=None, entries=(), top=None, idle_warn=60, checks=()):
    """The part of the page that is made again at every refresh: when, then the cards or the error, then
    what podium has run. top is everything conduct status --json printed (for whether it read the listing
    of live sessions); idle_warn, the minutes at which an idle session is marked; checks, what became of
    the Starts podium sent (start_checks)."""
    parts = [f'<p class="asof">As of {now:%H:%M:%S} UTC</p>']
    if error:
        return parts[0] + f'<p class="error">{e(error)}</p>' + activity(entries, checks)
    if not rows:
        return parts[0] + '<p class="empty">No mailboxes.</p>' + activity(entries, checks)
    some_wait = any(r["state"] in ASLEEP and not watching(r) for r in rows
                    if r["mailbox"] != "bernstein" and r["kind"] != "conductor")
    lost = [r["mailbox"] for r in rows if r["mailbox"] != "bernstein" and r["kind"] != "conductor"
            and r["state"] in ASLEEP and not watching(r) and alive(r) is not None]
    one = len(lost) == 1
    passed = (f"{joined(lost)} {'is' if one else 'are'} alive but not watching mail: conduct passes a stale duty "
              f"over and sends {'it' if one else 'them'} nothing. Speak to {'it' if one else 'them'} in the app."
              ) if lost else ""
    for_all = "".join(f'<button type="button" class="act" data-verb="{verb}" data-all="1"'
                      f'{noted((SOME_WAKES_WAIT if some_wait else "") if verb == "wake" else passed)}>'
                      f"{LABELS[verb]} all</button>" for verb in buttons_for_all(rows))
    if for_all:
        parts.append(f'<div class="all">{for_all}</div>')
    found = groups(rows)
    pointed = {r["mailbox"] for _head, _claws, labels in found["cards"] for r, _what in labels}

    listing = top.get("live_listing") if isinstance(top, dict) else None
    unread = isinstance(listing, dict) and listing.get("read") is False

    on_line = {found["project"]: found for found in checks if found["line"]}

    def line(r, label=None, claw=False):
        return row_html(r, now, label, claw, anchor=r["mailbox"] in pointed, unread=unread, idle_warn=idle_warn,
                        check=on_line.get(r["mailbox"]))

    for head, claws, labels in found["cards"]:
        parts.append('<section class="card">' + line(head)
                     + "".join(line(c, label, claw=True) for c, label in claws) + labels_html(labels, now)
                     + "</section>")
    for title, members in (("Claws", found["claws"]),
                           ("Cannot be started", [(r, None) for r in found["unstartable"]]),
                           ("bernstein", [(found["bernstein"], None)] if found["bernstein"] else [])):
        if members:
            parts.append(f'<h2>{title}</h2><section class="card">'
                         + "".join(line(r, said) for r, said in members) + "</section>")
    if found["conductors"]:
        parts.append("<h2>Conductor</h2>")
    for head, claws in found["conductors"]:
        parts.append('<section class="card">' + line(head)
                     + "".join(line(c, label, claw=True) for c, label in claws) + "</section>")
    return "".join(parts) + activity(entries, checks)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>podium</title>
<style>
:root {
  --bg: #F4F0EE; --card: #FFFFFF; --ink: #333333; --muted: #6E6661; --line: #DED5CE;
  --accent: #D15727; --small-accent: #A6451F; --fill: #A6451F; --tint: #F3D2C2; --on: #FFFFFF;
  --mistake: #A51E22; --mistake-text: #A51E22; --correct: #3B7A55; --gold: #A6904B;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #211D1B; --card: #2B2623; --ink: #F4F0EE; --muted: #B8ADA5; --line: #4A413B;
    --small-accent: #F0A283; --tint: #5A3324; --mistake-text: #F2A0A3;
  }
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.35 "EB Garamond", Georgia, serif; font-size-adjust: 0.45; }
.page { max-width: 60rem; margin: 0 auto; padding: 14px 16px 32px; }
.top { display: flex; align-items: center; gap: 10px; }
.mark { flex: none; width: 30px; height: 30px; border-radius: 50%; background: var(--accent); color: var(--on);
  font-weight: 600; font-size: 19px; line-height: 30px; text-align: center; }
h1 { font-size: 26px; font-weight: 600; margin: 0; line-height: 1; }
.top button { margin-left: auto; }
h2, .asof { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--small-accent); }
h2 { margin: 14px 0 5px; }
.asof { margin: 8px 0 12px; font-variant-numeric: tabular-nums; }
.asof::after { content: ""; display: block; width: 9rem; height: 3px; background: var(--accent); margin-top: 6px; }
button, a.open { font: inherit; font-size: 15px; color: var(--small-accent); background: var(--card);
  border: 1px solid var(--line); border-radius: 999px; padding: 1px 11px; cursor: pointer; white-space: nowrap; }
a.open { text-decoration: none; color: var(--ink); }
button:hover:not(:disabled), a.open:hover { background: var(--fill); border-color: var(--fill); color: var(--on); }
button:focus-visible, a.open:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button:disabled { opacity: 0.5; cursor: default; }
#act-go { background: var(--fill); border-color: var(--fill); color: var(--on); }
.lost, .error { background: var(--mistake); color: var(--on); border-radius: 6px; padding: 7px 12px;
  margin: 0 0 10px; white-space: pre-wrap; }
.empty { color: var(--muted); font-style: italic; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 6px; margin: 0 0 8px;
  overflow: hidden; }
.row { display: grid; grid-template-columns: minmax(9rem, 1fr) 11.5rem minmax(0, 1.5fr) 15.5rem;
  gap: 2px 12px; align-items: center; padding: 5px 12px; }
.row + .row { border-top: 1px solid var(--line); }
.row.claw .who { padding-left: 16px; }
.who { min-width: 0; }
.name { font-weight: 600; overflow-wrap: anywhere; }
.row.claw .name { font-weight: 500; }
.kind { color: var(--muted); font-style: italic; font-size: 15px; }
.badge { justify-self: start; font-size: 14px; font-weight: 600; line-height: 1.45; border-radius: 11px;
  padding: 0 9px; border: 1px solid var(--line); color: var(--muted); background: transparent; }
.badge.ok { background: var(--correct); border-color: var(--correct); color: var(--on); }
.badge.busy { background: var(--fill); border-color: var(--fill); color: var(--on); }
.badge.sleep { background: var(--ink); border-color: var(--ink); color: var(--bg); }
.badge.warn { border-color: var(--gold); border-width: 2px; color: var(--ink); }
.badge.alert { background: var(--mistake); border-color: var(--mistake); color: var(--on); }
.facts { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0 12px;
  color: var(--muted); font-size: 15px; font-variant-numeric: tabular-nums; grid-column: 3; }
.facts .new { color: var(--ink); font-weight: 600; }
.facts .context { display: inline-flex; align-items: center; gap: 6px; }
.facts .context .bar { width: 3.5rem; height: 0.5rem; flex: none; border: 1px solid var(--muted);
  border-radius: 4px; background: transparent; }
.facts .context .fill { fill: var(--muted); }
.facts .context.warn { color: var(--ink); font-weight: 600; border: 2px solid var(--gold); border-radius: 11px;
  padding: 0 7px; }
.facts .context.warn .bar { border-color: var(--mistake-text); }
.facts .context.warn .fill { fill: var(--mistake-text); }
.facts .context.unknown, .facts .live.unknown { font-style: italic; }
.facts .live.long, .facts .live.several, .facts .live.lower { color: var(--ink); font-weight: 600;
  border: 2px solid var(--gold); border-radius: 11px; padding: 0 7px; }
.labels { display: flex; flex-wrap: wrap; gap: 5px 8px; padding: 5px 12px 6px 28px;
  border-top: 1px solid var(--line); }
a.label { display: inline-flex; align-items: center; gap: 2px 6px; font-size: 15px; color: var(--ink);
  text-decoration: none; border: 1px solid var(--line); border-radius: 11px; padding: 1px 3px 1px 10px;
  flex-wrap: wrap; white-space: nowrap; max-width: 100%; }
a.label .badge { font-size: 13px; white-space: normal; }
a.label:hover { border-color: var(--fill); }
a.label:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.row:target { background: var(--tint); }
.refused { grid-column: 1 / -1; margin: 0; color: var(--mistake-text); font-size: 15px; overflow-wrap: anywhere; }
.acts, .all { display: flex; flex-wrap: wrap; gap: 5px; }
.acts { grid-column: 4; justify-content: flex-end; }
.all { margin: 0 0 10px; }
.log .run { padding: 6px 12px; }
.remind { margin: 4px 0 0; font-size: 15px; color: var(--muted); }
.started { grid-column: 1 / -1; margin: 4px 0 0; font-size: 15px; color: var(--muted); overflow-wrap: anywhere; }
.started.right { color: var(--ink); }
.started.right::before { content: "\\2713\\00a0"; color: var(--correct); font-weight: 600; }
.started.wrong { color: var(--mistake-text); font-weight: 600; border: 2px solid var(--mistake-text);
  border-radius: 6px; padding: 3px 8px; }
.log .run + .run { border-top: 1px solid var(--line); }
.what { margin: 0 0 3px; display: flex; flex-wrap: wrap; gap: 2px 10px; align-items: center; }
.time { color: var(--muted); font-size: 15px; font-variant-numeric: tabular-nums; }
code, pre { font: 12.5px/1.45 "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size-adjust: none; }
code { overflow-wrap: anywhere; }
pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--muted); }
dialog { width: min(42rem, calc(100% - 32px)); max-height: calc(100% - 32px); overflow: auto; color: var(--ink);
  background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 16px 18px; }
dialog::backdrop { background: rgba(51, 51, 51, 0.5); }
dialog h2 { font-size: 22px; text-transform: none; letter-spacing: 0; color: var(--ink); margin: 0 0 10px; }
dialog label, dialog legend { display: block; font-size: 15px; color: var(--muted); margin: 0 0 3px; padding: 0; }
dialog fieldset { border: 0; padding: 0; margin: 0 0 10px; }
dialog .choice { display: flex; gap: 8px; align-items: baseline; color: var(--ink); font-size: 17px; margin: 0; }
dialog .field { margin: 0 0 10px; }
textarea, select, input[type="number"] { font: inherit; color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 6px; padding: 3px 8px; }
input[type="radio"] { accent-color: var(--accent); }
textarea { width: 100%; min-height: 6rem; resize: vertical; }
input[type="number"] { width: 6rem; }
.shown { background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px;
  margin: 0 0 10px; }
.shown code { display: block; color: var(--ink); margin: 0 0 5px; }
.note { margin: 0 0 10px; }
.progress { display: flex; align-items: center; gap: 10px; margin: 0 0 10px; font-variant-numeric: tabular-nums; }
.spin { flex: none; width: 16px; height: 16px; border-radius: 50%; border: 2px solid var(--line);
  border-top-color: var(--accent); animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
.buttons { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.buttons button { font-size: 17px; padding: 2px 16px; }
@media (max-width: 640px) {
  .row { grid-template-columns: 1fr auto; }
  .who { min-width: 9rem; }
  .facts, .acts { grid-column: 1 / -1; }
  .acts { justify-content: flex-start; padding-bottom: 2px; }
  .row.claw .who { padding-left: 12px; }
  .labels { padding-left: 24px; }
}
</style>
</head>
<body>
<div class="page">
<header class="top"><span class="mark" aria-hidden="true">P</span><h1>podium</h1><button id="refresh" type="button">Refresh</button></header>
<p id="lost" class="lost" hidden></p>
<main id="view">%%VIEW%%</main>
</div>
<dialog id="act" aria-labelledby="act-title">
<h2 id="act-title"></h2>
<p id="act-waits" class="note" hidden></p>
<div id="act-options"></div>
<div id="act-shown" class="shown" hidden><code id="act-command"></code><pre id="act-output"></pre></div>
<p id="act-progress" class="progress" role="status" hidden><span class="spin"></span><span id="act-progress-text"></span></p>
<p id="act-note" class="note" hidden></p>
<p id="act-problem" class="error" hidden></p>
<div class="buttons"><button type="button" id="act-cancel">Cancel</button><button type="button" id="act-go">Send</button></div>
</dialog>
<script>
(function () {
  var token = new URLSearchParams(location.search).get("t") || "";
  var lost = document.getElementById("lost");
  var dialog = document.getElementById("act");
  var title = document.getElementById("act-title");
  var options = document.getElementById("act-options");
  var shown = document.getElementById("act-shown");
  var command = document.getElementById("act-command");
  var output = document.getElementById("act-output");
  var note = document.getElementById("act-note");
  var waits = document.getElementById("act-waits");
  var progress = document.getElementById("act-progress");
  var progressText = document.getElementById("act-progress-text");
  var ticking = null;    // the timer that counts the seconds while conduct runs
  var problem = document.getElementById("act-problem");
  var cancel = document.getElementById("act-cancel");
  var go = document.getElementById("act-go");
  var names = {start: "Start", stop: "Stop", dormant: "Dormant", wake: "Wake", dream: "Dream"};
  var asked = null;      // {verb, project} or {verb, all: true}: what the open dialog is about
  var step = "options";  // options, then done

  function refresh() {
    return fetch("/view?t=" + encodeURIComponent(token), {cache: "no-store"}).then(function (answer) {
      if (!answer.ok) { throw new Error("it answered " + answer.status); }
      return answer.text();
    }).then(function (made) {
      document.getElementById("view").innerHTML = made;
      lost.hidden = true;
    }).catch(function (why) {
      lost.textContent = "podium is not answering (" + why.message + "). Is its Terminal command still running?";
      lost.hidden = false;
    });
  }

  function post(path, body) {
    body.t = token;
    return fetch(path, {method: "POST", cache: "no-store", headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(body)}).then(function (answer) {
      return answer.text().then(function (text) {
        var said;
        try { said = JSON.parse(text); } catch (notJson) { said = {error: text.trim() || "podium answered " + answer.status}; }
        return {ok: answer.ok, said: said};
      });
    }, function (why) {
      return {ok: false, said: {error: "podium is not answering (" + why.message + "). Is its Terminal command still running?"}};
    });
  }

  function add(parent, tag, text, attributes) {
    var made = document.createElement(tag);
    if (text) { made.textContent = text; }
    Object.keys(attributes || {}).forEach(function (name) { made.setAttribute(name, attributes[name]); });
    parent.appendChild(made);
    return made;
  }

  function field(labelText, id) {
    var holder = add(options, "div", "", {"class": "field"});
    add(holder, "label", labelText, {"for": id});
    return holder;
  }

  function choice(parent, name, value, text, checked) {
    var line = add(parent, "label", "", {"class": "choice"});
    var radio = add(line, "input", "", {type: "radio", name: name, value: value});
    radio.checked = checked;
    add(line, "span", text);
    return radio;
  }

  function minutesField(labelText) {
    return add(field(labelText, "act-minutes"), "input", "",
               {type: "number", id: "act-minutes", min: "5", max: "240", value: "60"});
  }

  function build(verb) {
    options.textContent = "";
    if (verb === "start") {
      add(field("A brief for the session (optional). It is sent word for word.", "act-brief"), "textarea", "",
          {id: "act-brief"});
      add(field("A name for the session in the app's list (optional; else the project and the day)", "act-name"),
          "input", "", {type: "text", id: "act-name", maxlength: "60"});
      var pace = add(field("Mail pace", "act-pace"), "select", "", {id: "act-pace"});
      add(pace, "option", "Leave as it is", {value: ""});
      ["eager", "normal", "relaxed"].forEach(function (level) { add(pace, "option", level, {value: level}); });
    } else if (verb === "stop") {
      var first = add(options, "fieldset", "");
      add(first, "legend", "Dream first?");
      choice(first, "act-dream", "no", "No: hand over and stop now", true);
      choice(first, "act-dream", "yes", "Yes: dream first, then hand over and stop", false);
      minutesField("Minutes to dream, if dreaming first (5 to 240)");
      add(field("Seconds to wait for the handover, if stopping now (optional, 1 to 600)", "act-wait"), "input", "",
          {type: "number", id: "act-wait", min: "1", max: "600"});
    } else if (verb === "dream") {
      minutesField("Minutes to dream (5 to 240)");
      var then = add(field("Afterwards", "act-then"), "select", "", {id: "act-then"});
      add(then, "option", "Go dormant", {value: "dormant"});
      add(then, "option", "Hand over and stop", {value: "stop"});
    }
  }

  function number(id) {
    var box = document.getElementById(id);
    if (!box || box.value.trim() === "") { return null; }
    return /^[0-9]+$/.test(box.value.trim()) ? parseInt(box.value.trim(), 10) : box.value;
  }

  function actionNow() {
    var action = {verb: asked.verb};
    if (asked.all) { action.all = true; } else { action.project = asked.project; }
    if (asked.verb === "start") {
      if (document.getElementById("act-brief").value !== "") { action.brief = document.getElementById("act-brief").value; }
      if (document.getElementById("act-pace").value !== "") { action.pace = document.getElementById("act-pace").value; }
      if (document.getElementById("act-name").value !== "") { action.name = document.getElementById("act-name").value; }
    } else if (asked.verb === "stop") {
      if (document.querySelector('input[name="act-dream"]:checked').value === "yes") {
        action.verb = "dream";
        action.then = "stop";
        action.minutes = number("act-minutes");
      } else if (number("act-wait") !== null) {
        action.wait = number("act-wait");
      }
    } else if (asked.verb === "dream") {
      action.minutes = number("act-minutes");
      action.then = document.getElementById("act-then").value;
    }
    if (action.minutes === null) { delete action.minutes; }
    return action;
  }

  function show(said) {
    command.textContent = said.command || "";
    output.textContent = (said.output || "") + (said.error || "");
    shown.hidden = false;
  }

  function trouble(text) {
    problem.textContent = text;
    problem.hidden = !text;
  }

  function working(what) {
    // what: words for what conduct is doing now, shown with the seconds so far; nothing when it has finished
    var began = Date.now();
    function tick() {
      var seconds = Math.floor((Date.now() - began) / 1000);
      progressText.textContent = what + "\u2026 " + seconds + " s";
    }
    if (ticking !== null) { clearInterval(ticking); ticking = null; }
    go.disabled = Boolean(what);
    cancel.disabled = Boolean(what);
    progress.hidden = !what;
    if (what) {
      tick();
      ticking = setInterval(tick, 1000);
    }
  }

  function send() {
    var action = actionNow();
    working("Sending: " + title.textContent +
            (action.wait ? " (it waits up to " + action.wait + " s for the handover)" : ""));
    trouble("");
    post("/run", {action: action}).then(function (got) {
      working("");
      if (!got.ok) {                     // podium refused it, or is busy: nothing was run, so it can be put right
        trouble(got.said.error || "podium refused that");
        return;
      }
      if (action.verb === "start" && got.said.exit === 0) { dialog.close(); return; }
      step = "done";
      options.hidden = true;
      go.hidden = true;
      cancel.textContent = "Close";
      show(got.said);
      if (got.said.exit === 0) {
        note.textContent = "Done." + (got.said.reminder ? " " + got.said.reminder : "");
        note.hidden = false;
      } else {
        trouble(got.said.exit === null ? "conduct did not finish." : "conduct failed (exit " + got.said.exit + ").");
      }
      if (got.said.log_error) { trouble((problem.textContent ? problem.textContent + " " : "") + got.said.log_error); }
    });
  }

  function open(verb, project, all, why) {
    asked = all ? {verb: verb, all: true} : {verb: verb, project: project};
    step = "options";
    title.textContent = names[verb] + " " + (all ? "every session but bernstein's" : project);
    build(verb);
    options.hidden = false;
    command.textContent = "";
    output.textContent = "";
    shown.hidden = true;
    note.hidden = true;
    waits.textContent = why || "";
    waits.hidden = !why;
    trouble("");
    working("");
    go.hidden = false;
    cancel.textContent = "Cancel";
    dialog.showModal();
  }

  document.getElementById("view").addEventListener("click", function (event) {
    var pressed = event.target.closest("button.act");
    if (pressed) {
      open(pressed.dataset.verb, pressed.dataset.project, pressed.dataset.all === "1", pressed.dataset.note);
    }
  });
  go.addEventListener("click", function () { if (step === "options") { send(); } });
  cancel.addEventListener("click", function () { dialog.close(); });
  dialog.addEventListener("close", function () { refresh(); });
  document.getElementById("refresh").addEventListener("click", refresh);
  setInterval(function () { if (!dialog.open) { refresh(); } }, 15000);
})();
</script>
</body>
</html>
"""


def page(made):
    """The whole page around a view. The view is made here, in Python; the page's script only fetches
    a new one and puts it in place."""
    return PAGE.replace("%%VIEW%%", made)


CONDUCT_SECONDS = 30


def ask_conduct(conduct, env, run=subprocess.run):
    """conduct status --json, as (rows, the text it printed, None), or ([], None, why it failed).
    conduct is run as an argument list, never through a shell."""
    try:
        done = run([conduct, "status", "--json"], env=env, capture_output=True, text=True, check=False,
                   timeout=CONDUCT_SECONDS)
    except subprocess.TimeoutExpired:
        return [], None, f"conduct status did not answer within {CONDUCT_SECONDS} seconds"
    except OSError as why:
        return [], None, f"{conduct} could not be run ({why.strerror})"
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()
        return [], None, f"conduct status failed (exit {done.returncode})" + ("\n  " + detail if detail else "")
    try:
        rows = json.loads(done.stdout)["mailboxes"]
        if not all(isinstance(r["mailbox"], str) and isinstance(r["state"], str) for r in rows):
            raise TypeError("not rows")
    except (ValueError, KeyError, TypeError):
        return [], None, "conduct status --json did not print the expected JSON"
    return rows, done.stdout, None


NO_TOKEN = (403, "text/plain",
            "podium: this address needs the token: open the link podium printed when it started\n")
BODY_LIMIT = 200000


def respond(method, target, token, fetch, now, entries=(), idle_warn=60, check=None):
    """(status, content type, body) for a request to look. Nothing is answered without the token; fetch,
    which asks conduct, is called only for an address that shows the listing. idle_warn is the minutes at
    which the page marks an idle session; check(rows, top, now) says what became of the Starts podium sent."""
    parts = urllib.parse.urlsplit(target)
    given = urllib.parse.parse_qs(parts.query, keep_blank_values=True).get("t", [])
    if len(given) != 1 or not hmac.compare_digest(given[0].encode("utf-8"), token.encode("utf-8")):
        return NO_TOKEN
    if method != "GET":
        return 405, "text/plain", "podium: this address answers GET and nothing else\n"
    if parts.path not in ("/", "/view", "/status"):
        return 404, "text/plain", "podium: there is nothing at this address\n"
    rows, raw, error = fetch()
    if parts.path == "/status":
        if error:
            return 502, "application/json", json.dumps({"error": error}) + "\n"
        return 200, "application/json", raw
    try:
        top = json.loads(raw) if raw else None
    except ValueError:
        top = None
    checks = check(rows, top, now) if check and not error else ()
    made = view(rows, now, error, entries, top=top, idle_warn=idle_warn, checks=checks)
    return 200, "text/html", page(made) if parts.path == "/" else made


def act(target, body, token, panel):
    """(status, content type, body) for a request to act: POST /run with an action, which is run at once.
    The token is in the body, and nothing is done without it."""
    if len(body) > BODY_LIMIT:
        return 413, "text/plain", "podium: that is more than podium takes in one request\n"
    try:
        sent = json.loads(body.decode("utf-8"))
    except ValueError:
        sent = None
    given = sent.get("t") if isinstance(sent, dict) else None
    if not isinstance(given, str) or not hmac.compare_digest(given.encode("utf-8"), token.encode("utf-8")):
        return NO_TOKEN
    path = urllib.parse.urlsplit(target).path
    if path != "/run":
        return 404, "text/plain", "podium: there is nothing to send to at this address\n"
    code, said = panel.send(sent.get("action"))
    return code, "application/json", json.dumps(said) + "\n"


def answer(method, target, body, token, panel, now):
    """The answer to any request: a POST acts, anything else looks. A fault of podium's own becomes a
    plain 500 instead of a traceback."""
    try:
        if method == "POST":
            return act(target, body, token, panel)
        return respond(method, target, token, panel.listing, now, panel.entries,
                       idle_warn=getattr(panel, "idle_warn", 60), check=getattr(panel, "checks", None))
    except Exception as fault:  # noqa: BLE001 - the last line of defence for a page someone is looking at
        return 500, "text/plain", (f"podium: something went wrong inside podium ({type(fault).__name__}: {fault}); "
                                   "try Refresh\n")


CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def handler_for(token, panel, clock):
    """The request handler: every method goes through answer, and nothing is logged to the terminal."""
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "podium"
        sys_version = ""
        timeout = 30

        def reply(self):
            try:
                length = max(0, int(self.headers.get("Content-Length") or 0))
            except ValueError:
                length = 0
            sent = self.rfile.read(min(length, BODY_LIMIT + 1)) if length else b""
            code, kind, body = answer(self.command, self.path, sent, token, panel, clock())
            data = body.encode("utf-8")
            self.send_response(code)
            for name, value in (("Content-Type", kind + "; charset=utf-8"), ("Content-Length", str(len(data))),
                                ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                                ("Referrer-Policy", "no-referrer"), ("Content-Security-Policy", CSP)):
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_OPTIONS = do_PATCH = reply

        def log_message(self, format, *args):
            pass

    return Handler


class Server(http.server.ThreadingHTTPServer):
    """One thread per request, so a browser's idle connection cannot hold the page up."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        """A connection the browser dropped is nothing to tell the terminal about."""


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="podium", description="A control panel for lobster sessions: a page on this machine only, "
               "served while this command runs, showing what conduct status shows.",
               epilog="podium [--port N] [--no-open]", formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", metavar="N", help="the port to serve on, 0 for any free one (setting PODIUM_PORT, "
                   "8417 unless set); if it is in use, a free one is used instead")
    p.add_argument("--no-open", action="store_true", help="do not open the page in the browser")
    return p


def conduct_beside():
    """The conduct command in the checkout this module is in."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conduct")


def listen(port, handler, make_server):
    """(server, the port asked for if it was in use and another was taken). 127.0.0.1 only."""
    try:
        return make_server(("127.0.0.1", port), handler), None
    except OSError as why:
        if why.errno != errno.EADDRINUSE or port == 0:
            raise
    return make_server(("127.0.0.1", 0), handler), port


def main(argv, env, out, err, conduct=None, token=None, serve=None, clock=None, make_server=Server):
    """Run podium; return its exit code. conduct is the command to ask, token the secret in the link,
    serve what runs the server until it is stopped, clock the time in UTC: all for tests to supply."""
    if argv[:1] in (["-h"], ["--help"]):
        out.write(parser().format_help())
        return 0
    try:
        path = env.get("BERNSTEIN_CONF") or os.path.join(env["HOME"], ".bernstein.conf")
        text = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
        try:
            s = read_settings(text, env["HOME"])
        except SettingsRefused as why:
            raise Stop(2, f"{path}: {why}")
        try:
            a = parser().parse_args(argv)
            if a.port is not None:
                check_port(a.port, "--port", shown=True)
        except SettingsRefused as why:
            raise Stop(2, f"{why} (podium --help shows the form)")
        port = int(a.port if a.port is not None else s["PODIUM_PORT"])
        token = token or secrets.token_urlsafe(32)
        conduct = conduct or conduct_beside()
        clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        handler = handler_for(token, Panel(conduct, env, clock, s["PODIUM_LOG"], idle_warn=int(s["IDLE_WARN"])),
                              clock)
        try:
            server, busy = listen(port, handler, make_server)
        except OSError as why:
            raise Stop(4, f"could not start serving on 127.0.0.1 port {port} ({why.strerror})")
    except Stop as stopped:
        err.write(f"podium: {stopped.message}\n")
        return stopped.code
    try:
        serving = server.server_address[1]
        if busy is not None:
            out.write(f"Port {busy} is in use: using {serving} instead.\n")
        link = f"http://127.0.0.1:{serving}/?t={urllib.parse.quote(token, safe='')}"
        out.write(f"podium is serving at {link}\nIt runs only while this command runs: stop it with Ctrl-C.\n")
        out.flush()   # the link must be readable now, also when the output is a file or a pipe
        if not a.no_open:
            open_in_browser(link, env, err)
        try:
            (serve or (lambda running: running.serve_forever()))(server)
        except KeyboardInterrupt:
            pass
        out.write("podium stopped.\n")
    finally:
        server.server_close()
    return 0


def open_in_browser(link, env, err):
    """Open the page with macOS's open. If that fails the page is still served: say so and carry on."""
    try:
        done = subprocess.run(["open", link], env=env, capture_output=True, text=True, check=False)
        why = None if done.returncode == 0 else (done.stderr or done.stdout).strip() or f"exit {done.returncode}"
    except OSError as failed:
        why = failed.strerror
    if why:
        err.write(f"podium: the page could not be opened in the browser ({why}); open the link above yourself\n")


class Refused(ValueError):
    """An action the page asked for that podium does not offer; the message says why."""


PACES = ("eager", "normal", "relaxed")
BRIEF_LIMIT = 20000
NAME_LIMIT = 60
OPTIONS = {"start": ("pace", "brief", "name"), "stop": ("wait",), "dormant": (), "wake": (), "dream": ("minutes", "then")}


def whole(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def command_for(action, names):
    """(conduct's arguments, the brief's text or None) for an action the page sent. Only the verbs and
    options podium offers, and only a project in the listing it last showed: anything else is Refused."""
    if not isinstance(action, dict):
        raise Refused("an action must be a JSON object")
    verb = action.get("verb")
    if not isinstance(verb, str) or verb not in OPTIONS:
        raise Refused(f"podium does not offer the verb {verb!r}")
    for key in action:
        if key not in ("verb", "project", "all") + OPTIONS[verb]:
            raise Refused(f"{verb} does not take {key}")
    project, everything = action.get("project"), action.get("all", False)
    if not isinstance(everything, bool) or everything == (project is not None):
        raise Refused("name one project, or everything at once")
    if everything:
        if verb == "start":
            raise Refused("start is for one project at a time")
        argv = [verb, "--all"]
    else:
        if not isinstance(project, str) or project not in names:
            raise Refused(f"{project!r} is not a mailbox in the listing podium last showed")
        if project == "bernstein":
            raise Refused("podium does not act on bernstein's own session")
        if project.startswith("-"):
            raise Refused(f"{project!r} cannot be given to conduct as a project: it starts with a dash")
        argv = [verb, project]
    brief = None
    if verb == "start":
        if action.get("pace") is not None:
            if action["pace"] not in PACES:
                raise Refused("the pace must be eager, normal or relaxed")
            argv += ["--pace", action["pace"]]
        brief = action.get("brief")
        if brief is not None and not isinstance(brief, str):
            raise Refused("the brief must be text")
        if brief is not None and len(brief) > BRIEF_LIMIT:
            raise Refused(f"the brief is longer than {BRIEF_LIMIT} characters")
        brief = brief or None
        name = action.get("name")
        if name is not None and not isinstance(name, str):
            raise Refused("the name must be text")
        if name is not None and name.strip():
            if "\n" in name or "\r" in name:
                raise Refused("the name must be one line")
            if len(name.strip()) > NAME_LIMIT:
                raise Refused(f"the name is longer than {NAME_LIMIT} characters")
            argv += ["--name=" + name.strip()]
    if verb == "stop" and action.get("wait") is not None:
        if not whole(action["wait"], 1, 600):
            raise Refused("the wait must be a whole number of seconds from 1 to 600")
        argv += ["--wait", str(action["wait"])]
    if verb == "dream":
        minutes, then = action.get("minutes", 60), action.get("then", "dormant")
        if not whole(minutes, 5, 240):
            raise Refused("the minutes must be a whole number from 5 to 240")
        if then not in ("dormant", "stop"):
            raise Refused("then must be dormant or stop")
        argv += ["--minutes", str(minutes), "--then", then]
    return argv, brief


def shown(argv, brief):
    """The command as it could be typed, for the page and the log. A brief is shown by its length."""
    text = "conduct " + " ".join(shlex.quote(a) for a in argv)
    if brief:
        text += f" --brief <the brief typed in podium, {len(brief)} characters>"
    return text


BUSY = (409, {"error": "podium is busy with another action: try again when it has finished"})
REMINDER = ("Now in the desktop app: confirm the folder or folders it shows, then send the first line. If it is a "
            "Claude Code session, check its folder is the project's before anything else (the app has dropped it "
            "before), and ask a bernstein session to set its model and effort.")


def log_text(entry):
    """One run as the log file keeps it: a line saying when, what and how it ended, then what it printed."""
    ended = f"exit {entry['exit']}" if entry["exit"] is not None else "not run"
    printed = "".join("  " + line + "\n" for line in (entry["output"] + entry["error"]).splitlines())
    return f"{entry['time']}  {entry['command']}  ({ended})\n{printed}"


class Panel:
    """What podium knows and does between requests: the names in the last listing, what it has run, and
    the one action that may run at a time. It runs conduct and nothing else, never with --dry-run (there
    is no preview since 15 November 2026: an action sent is run), and writes only the brief's temporary
    file and the log."""

    def __init__(self, conduct, env, clock, log_path, run=subprocess.run, idle_warn=60):
        self.conduct, self.env, self.clock, self.log_path, self.run = conduct, env, clock, log_path, run
        self.idle_warn = idle_warn      # the minutes at which the page marks an idle session (IDLE_WARN)
        self.starts = {}                # the Starts that worked, by project, for start_checks: in memory only
        self.names, self.entries = None, []
        self.lock = threading.Lock()

    def listing(self):
        """conduct status --json, remembering the mailboxes it names for the actions that follow."""
        rows, raw, error = ask_conduct(self.conduct, self.env, self.run)
        if not error:
            self.names = {r["mailbox"] for r in rows}
        return rows, raw, error

    def checks(self, rows, top, now):
        """What became of the Starts podium sent, from the listing just read (start_checks)."""
        return start_checks(self.starts, rows, top, now)

    def call(self, argv, brief):
        """Run conduct with these arguments: (exit code or None if it did not run to the end, what it
        printed, what it said on standard error or why it did not run). The brief is a file while it runs."""
        seconds = 60 + (int(argv[argv.index("--wait") + 1]) if "--wait" in argv else 0)
        full, path = [self.conduct, *argv], None
        try:
            if brief:
                handle, path = tempfile.mkstemp(prefix="podium-brief-", suffix=".txt")
                with os.fdopen(handle, "w", encoding="utf-8") as f:
                    f.write(brief)
                full += ["--brief", path]
            try:
                done = self.run(full, env=self.env, capture_output=True, text=True, check=False, timeout=seconds)
            except subprocess.TimeoutExpired:
                return None, "", (f"conduct was stopped after {seconds} seconds without finishing; some of it may "
                                  "have been done: look at the page before trying again")
            except OSError as why:
                return None, "", f"{self.conduct} could not be run ({why.strerror})"
            return done.returncode, done.stdout, done.stderr
        finally:
            if path:
                os.remove(path)

    def send(self, action):
        """(status, the run as recorded) for an action the page sent: it is run for real, at once."""
        if not self.lock.acquire(blocking=False):
            return BUSY
        try:
            if self.names is None:
                self.listing()
            try:
                argv, brief = command_for(action, self.names or set())
            except Refused as why:
                return 400, {"error": str(why)}
            began = self.clock() if argv[0] == "start" else None      # a new session can only be later than this
            code, output, error = self.call(argv, brief)
            if began is not None and code == 0:
                self.starts.pop(argv[1], None)                          # a later Start takes the earlier one's place
                self.starts[argv[1]] = {"at": began.replace(microsecond=0), "entry": len(self.entries),
                                        "right": None}
            entry = {"time": f"{self.clock():%Y-%m-%dT%H:%M:%SZ}", "command": shown(argv, brief), "exit": code,
                     "output": output, "error": error,
                     "reminder": REMINDER if argv[0] == "start" and code == 0 else None, "log_error": None}
            try:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as log:
                    log.write(log_text(entry))
            except OSError as why:
                entry["log_error"] = f"the log {self.log_path} could not be written ({why.strerror})"
            self.entries.append(entry)
            return 200, entry
        finally:
            self.lock.release()
