"""How full a Claude Code session's context window is, read from the desktop app's own files.

PLAN.md ("How full a session's context window is") is the specification. Everything here only reads:
the app's store of sessions, for the name of a session's transcript, and the end of that transcript, for
the figures of its newest reply. The files are the app's, not ours: whatever is missing or not the
shape expected gives None ("not known"), never an error and never a figure worked out some other way.
"""

import datetime
import glob
import json
import os
import re

BLOCK = 1 << 20     # a transcript can be many megabytes, and the newest reply is near its end

SESSION_ID = re.compile(r"local_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TRANSCRIPT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
FIGURES = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def transcript_of(store, transcripts, session_id):
    """The one transcript of a Claude Code session: the store's entry for the session names it. None
    when the entry or the transcript is not there, is there twice, or the entry does not name one."""
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        return None
    entries = glob.glob(os.path.join(glob.escape(store), "*", "*", session_id + ".json"))
    if len(entries) != 1:
        return None
    try:
        with open(entries[0], encoding="utf-8") as f:
            name = json.load(f)["cliSessionId"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(name, str) or not TRANSCRIPT_ID.fullmatch(name):
        return None
    found = glob.glob(os.path.join(glob.escape(transcripts), "*", name + ".jsonl"))
    return found[0] if len(found) == 1 else None      # a folder of that name fails to open: not known


def lines_from_the_end(path, block=BLOCK):
    """The lines of a file as bytes, the last first, reading a block at a time from its end."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        at, tail = f.tell(), b""
        while at > 0:
            size = min(block, at)
            at -= size
            f.seek(at)
            lines = (f.read(size) + tail).split(b"\n")
            tail = lines[0]         # perhaps only the end of a line that begins in an earlier block
            yield from reversed(lines[1:])
        yield tail


def newest_reply(path, block=BLOCK):
    """The newest reply in a transcript that is not a sub-agent's, as the line holds it, or None. A line
    that is not JSON is passed over: the app may be half-way through writing the last one."""
    for line in lines_from_the_end(path, block):
        if b"assistant" not in line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("type") == "assistant" and not row.get("isSidechain"):
            return row
    return None


def figures_of(row):
    """(tokens in use, the time they are true for) from a reply, or None when it is not the shape expected."""
    try:
        usage, when = row["message"]["usage"], row["timestamp"]
        counts = [usage[key] for key in FIGURES]
    except (KeyError, TypeError):
        return None
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in counts) or sum(counts) == 0:
        return None
    if not isinstance(when, str):
        return None
    for form in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return sum(counts), f"{datetime.datetime.strptime(when, form):%Y-%m-%dT%H:%M:%SZ}"
        except ValueError:
            continue
    return None


def percent(tokens, window):
    """tokens as a whole percentage of window, a half rounded up."""
    return (200 * tokens + window) // (2 * window)


def context_of(store, transcripts, session, window, warn, block=BLOCK):
    """What conduct status --json says of a session's context window: tokens, window, percent, as_of and
    warn, or None. session is the row's own (app_sessions' or cowork_sessions'); only a Claude Code one
    has a transcript here. window and warn are the settings CONTEXT_WINDOW and CONTEXT_WARN, as numbers."""
    if not isinstance(session, dict) or session.get("app") != "code":
        return None
    path = transcript_of(store, transcripts, session.get("id"))
    if path is None:
        return None
    try:
        row = newest_reply(path, block)
    except OSError:
        return None
    found = figures_of(row) if row is not None else None
    if found is None:
        return None
    tokens, as_of = found
    share = percent(tokens, window)
    return {"tokens": tokens, "window": window, "percent": share, "as_of": as_of, "warn": share >= warn}
