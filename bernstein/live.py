"""Which Claude Code sessions are alive on the Mac, from `claude agents --json`.

PLAN.md ("Whether a session is alive") is the specification. A duty's heartbeat says that a mail watch is
running; this says whether the session itself is alive. Everything here only reads: the one command is
`claude agents --json`, which lists the sessions and uses no model. The listing is the `claude` command's
own, not ours: what is missing or not the type expected is "not known" (None), and a listing that cannot
be read at all gives a reason and no sessions, never an error.
"""

import datetime
import json
import os
import subprocess

LIMIT = 5           # seconds: the listing comes at once, so one that has not come by then is not coming


def started(value):
    """`startedAt` (milliseconds) as lobster-mail's UTC stamp, or None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    try:
        when = datetime.datetime.fromtimestamp(value / 1000, datetime.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return f"{when:%Y-%m-%dT%H:%M:%SZ}"


def words(entry, key):
    """One fact of a listed session that should be text, or None."""
    return entry[key] if isinstance(entry.get(key), str) else None


def sessions(text):
    """{real folder: its sessions, oldest first} from what `claude agents --json` printed. ValueError when
    that is not a JSON array; an entry that is not an object with a folder is passed over."""
    listed = json.loads(text)
    if not isinstance(listed, list):
        raise ValueError("not an array")        # noqa: TRY004 (one error for every listing that cannot be read)
    found = {}
    for entry in listed:
        if not isinstance(entry, dict) or not isinstance(entry.get("cwd"), str) or not entry["cwd"]:
            continue
        pid = entry.get("pid")
        found.setdefault(os.path.realpath(entry["cwd"]), []).append({
            "name": words(entry, "name"), "status": words(entry, "status"), "kind": words(entry, "kind"),
            "pid": pid if isinstance(pid, int) and not isinstance(pid, bool) else None,
            "started": started(entry.get("startedAt")), "id": words(entry, "sessionId")})
    for there in found.values():
        there.sort(key=lambda session: session["started"] or "")
    return found


def read(command, env, run=subprocess.run, limit=LIMIT):
    """(the sessions by real folder, None), or (None, why the listing could not be read). The command is
    run once, with `agents --json` and nothing else, and given `limit` seconds."""
    asked = f"{command} agents --json"
    try:
        done = run([command, "agents", "--json"], env=env, capture_output=True, text=True, check=False,
                   timeout=limit, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return None, f"{command} was not found"
    except OSError as why:
        return None, f"{command} could not be run ({why.strerror})"
    except subprocess.TimeoutExpired:
        return None, f"{asked} gave no answer in {limit} seconds"
    if done.returncode != 0:
        return None, f"{asked} failed (exit {done.returncode})"
    try:
        return sessions(done.stdout), None
    except ValueError:
        return None, f"{asked} did not print the expected JSON"


def label(session):
    """A session's name for a list of names: with its kind when it is not an interactive one."""
    name = session["name"] if session["name"] is not None else "a session with no name"
    return name if session["kind"] in (None, "interactive") else f"{name} ({session['kind']})"


def there(found, folder):
    """The sessions alive in a project's folder, oldest first: those whose folder is the same real path."""
    return found.get(os.path.realpath(folder), [])


def of(found, folder):
    """What conduct status --json says is alive in a project's folder: the newest interactive session
    there (the newest of any kind, when none is interactive), with how many there are (and each name, when
    more than one), or None when there is none."""
    alive = there(found, folder)
    if not alive:
        return None
    newest = next((session for session in reversed(alive) if session["kind"] == "interactive"), alive[-1])
    said = {"name": newest["name"], "status": newest["status"], "kind": newest["kind"],
            "started": newest["started"], "pid": newest["pid"], "count": len(alive)}
    if len(alive) > 1:
        said["names"] = [label(session) for session in alive]
    return said


def note(state, duty, handover_waiting, count):
    """The sentence where a mailbox's duty and the listing disagree, or None. state is conduct's word for
    the mailbox (quiet: a stale duty at the relaxed pace, which is normal there)."""
    if duty is None:
        said = None if not count else (
            "alive after its handover: not archived" if handover_waiting else "alive, not on duty")
    elif not duty.get("stale"):
        said = None if count else "no session alive, though its duty is fresh: a watch has outlived its session"
    elif not count:
        said = "no session alive: it ended without a handover"
    else:
        said = None if state == "quiet" else "alive, not watching mail"
    if count > 1:
        several = f"{count} sessions alive in its folder"
        said = several if said is None else f"{said}; {several}"
    return said


def shown(session):
    """One session in brackets: its name as JSON, its status, and its kind when it is not interactive."""
    name = ("a session with no name" if session["name"] is None
            else json.dumps(session["name"], ensure_ascii=False))
    parts = [name, session["status"] if session["status"] is not None else "status not known"]
    if session["kind"] not in (None, "interactive"):
        parts.append(session["kind"])
    return ", ".join(parts)


def text(alive, said, each):
    """The field in conduct status's text for a project on the Mac: the note, or "alive", or "no session
    alive", and each session alive there in brackets."""
    lead = said or ("alive" if alive else "no session alive")
    return lead + (" ({})".format("; ".join(shown(session) for session in each)) if each else "")
