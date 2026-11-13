"""conduct: start a lobster project's session, or ask a running one to hand over and stop.

PLAN.md ("The start and stop tool", "As built") is the specification. Exit codes: 0 done, 2 bad
arguments or settings, 3 no such project or mailbox (or, for start, a session already running),
4 a program failed or the duty listing could not be read, 5 --wait ran out.
"""

import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import urllib.parse
from types import SimpleNamespace

from bernstein import globalfiles
from bernstein.render import MONTHS, TemplateRefused
from bernstein.settings import SettingsRefused, read_settings

PACES = ("eager", "normal", "relaxed")
WAIT_STEP = 10
CHANGING_TRIES = 3
DELIVERED = 7  # lobster-mail: delivered, but the sender's sent copy could not be written


class ProjectRefused(ValueError):
    """The project cannot be found; the message says why."""


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def day(today):
    return f"{today.day} {MONTHS[today.month - 1]} {today.year}"


NAME_LIMIT = 60


def session_name(project, today, given=None):
    """What the session is called in the app's list: the name given, or the project and the day."""
    if given is not None:
        return given.strip()
    return f"{project} · {today.day} {MONTHS[today.month - 1]}"


def name_refusal(text):
    """Why a name given for a session cannot be used, or None."""
    if not text.strip():
        return "the name is empty"
    if "\n" in text or "\r" in text:
        return "the name must be one line"
    if len(text.strip()) > NAME_LIMIT:
        return f"the name is longer than {NAME_LIMIT} characters"
    return None


def start_message(brief, today, name, updated=(), kept=None, can_rename=True):
    """The body of the Start message: follow START-HERE.txt, name the session (a Claude Code session can
    give itself its name; a Claude Cowork session cannot), say which global files bernstein has just
    replaced, then the brief or wait."""
    text = (f"Start (from bernstein, {day(today)}).\n\n"
            "Squirrel has started this session through bernstein. Follow START-HERE.txt in this\n"
            "project's folder from the top: step 0 (the model and effort question) first, then the\n"
            "mail and the rest. If lobster-mail start says a status is being reported for this mailbox, an\n"
            "earlier session left it: clear it with the command start prints.\n\n")
    if can_rename:
        text += (f"This session's name is \"{name}\". If you have a tool that names or renames a\n"
                 "session, give this session (\"self\") exactly that title now, so Squirrel can find it in his list;\n"
                 "if you have no such tool, say so in your reply to this message.\n\n")
    else:
        text += (f"This session's name is \"{name}\": the first line Squirrel sent begins with it, so\n"
                 "that the app titles the session from it. A Claude Cowork session has no tool for naming a session,\n"
                 "so there is nothing to do or to report about the name.\n\n")
    if updated:
        text += ("bernstein brought this project's global files up to date just before this session started:\n"
                 f"{', '.join(updated)}. They are the template's and are never edited here; the copies they "
                 f"replaced are in\n_to_delete/{os.path.basename(kept)}/. Read them as they are now, say so in "
                 "the diary,\nand commit them with your next commit.\n\n")
    if brief is None:
        return text + "Then wait for Squirrel.\n"
    return text + "Then this brief, from Squirrel:\n\n" + brief


def finish_message(today):
    """The body of the Finish message: a feeler's one job is done; write it up, offer its scripts, hand over."""
    return (f"Finish (from bernstein, {day(today)}).\n\n"
            "Squirrel has asked this feeler to finish: its one job is done, or as done as it will be. At the\n"
            "next safe point:\n\n"
            "1. Write what was found, plainly, in CLAUDE.md under \"What was found\": the answer first, then\n"
            "   what it rests on, what is unsure, and where each file is.\n"
            "2. List every script in tools/ with what it did and a proposal for each: offer it to a claw (name\n"
            "   the claw; the request goes by mail on Squirrel's OK), or leave it here as a record. Run nothing\n"
            "   new for this.\n"
            "3. Bring \"Where things stand\" up to date, commit, and send the handover as START-HERE.txt says.\n"
            "4. Reply to this message with what was found in two lines and the scripts you propose to offer.\n"
            "5. Last of all, archive this session if you have a tool that archives a session; if you have\n"
            "   none, say so in your last line to him.\n\n"
            "Squirrel moves the folder to not-current/ himself when he has read the reply.\n")


def stop_message(today):
    """The body of the Stop message: hand over at the next safe point, then archive the session."""
    return (f"Stop (from bernstein, {day(today)}).\n\n"
            "Squirrel has asked this session to hand over and stop. At the next safe point (nothing\n"
            "half-edited, nothing half-committed): bring the record up to date, send the handover with\n"
            "lobster-mail handover, stop watching mail and stop the check-in chain, tell Squirrel in\n"
            "chat that bernstein asked you to hand over, and do nothing more unless he says.\n\n"
            "Then, as the very last thing, after your reply to this message: archive this session, so it\n"
            "leaves his list of sessions. In Claude Code in the desktop app that is the archive tool with\n"
            "the session \"self\", which he approves on the card the app shows; nothing may still be\n"
            "running in the background when you call it. If you have no tool that archives a session, say\n"
            "so in your last line to him instead.\n")


def dormant_message(project, today):
    """The body of the Dormant message: keep running, stop watching mail, no handover."""
    return (f"Dormant (from bernstein, {day(today)}).\n\n"
            "Squirrel has asked this session to go dormant until he comes back: keep running, keep\n"
            f"everything as it is, and do not hand over. First say so: run lobster-mail status --as {project}\n"
            "--session <your session> dormant. Then stop watching mail (stop the background wait, or the\n"
            "check-in chain) and run no mail checks; this mailbox's pace is being set to relaxed, so\n"
            f"lobster-mail pace --as {project} shows it. Ask Squirrel nothing until he next speaks to you: no\n"
            f"question, no offer, no reminder. When he does, run lobster-mail status --as {project} --session\n"
            f"<your session> --clear and lobster-mail pace --as {project} normal, start watching again as that\n"
            "prints, read the mail that arrived meanwhile, and tell him you are back.\n"
            "Nothing else changes.\n")


def wake_message(project, today):
    """The body of the Wake message: the pace is normal again, watch mail again."""
    return (f"Wake (from bernstein, {day(today)}).\n\n"
            f"Squirrel is back: this mailbox's pace is normal again. Run lobster-mail status --as {project}\n"
            "--session <your session> --clear, so you no longer report dormant; then lobster-mail pace --as\n"
            f"{project}, and do what it prints (start the background wait, or the check-in chain), read the\n"
            "mail that arrived while you were dormant, report it, and carry on.\n")


def until(now, minutes):
    """When a dream that starts now ends: "HH:MM UTC", with the day when it is not today's."""
    end = now + datetime.timedelta(minutes=minutes)
    text = f"{end:%H:%M} UTC"
    return text if end.date() == now.date() else f"{text} on {day(end)}"


def dream_subject(now, minutes):
    return f"Dream: until {until(now, minutes)}"


DREAM_BODY = """Squirrel has asked this session to dream until {until} ({minutes} minutes): to look back over its recent work
and write down proposals for him to review. Proposals only: change nothing else.

1. Say so, then mail while dreaming. Run lobster-mail status --as {project} --session <your session>
   dreaming --until {stamp}. Stop the background wait or the check-in chain, and watch for
   bernstein only:
   lobster-mail wait --as {project} --session <your session> --from bernstein in the background, or
   lobster-mail checkin --as {project} --session <your session> --from bernstein between steps where a
   background command cannot run. Claim and act on bernstein's mail only; leave every other message
   unclaimed and unread until the dream is over. A Stop from bernstein ends the dream early: write what
   you have, then do the Stop.
2. Read what has happened since your last dream (the newest file in dreams/, dreams/done/ or
   dreams/discarded/), or in the last seven days if there is none: the diary's log, your handovers and
   finished mail, the git log, inbox/done/, and your own rules (CLAUDE.md, START-HERE.txt, PLAN.md's
   decisions).
3. Look for anything that would make this project work better or faster: rules to merge (one concise rule
   is better than two or more verbose ones, and shorter reading at startup is a main aim), repeated
   actions to make into tools, corrections Squirrel has given more than once, surprises that keep coming
   back, and anything else. Be expansive and creative: a few silly ideas are better than filtering out a
   good one that seems extravagant at first. In a non-code project, draft each tool idea as a request to
   its tools project or a claw, in the usual form (the need, the ask, test ideas), but do not send it.
4. Write one file per topic in dreams/ in this project's folder, named {date}-<topic>.md: what you
   propose, why (with evidence: diary dates, message ids), the exact change (the full text of a new or
   merged rule, the request as it would be sent), and how many words it adds to or takes off what a
   session reads at startup. A file holds everything that belongs together, such as a tool request and
   the startup step that would use it. Write nothing else: no change to CLAUDE.md, START-HERE.txt,
   PLAN.md or any other rule, no request sent, no ticket, no commit; dreams/ stays out of git.
5. Check the time (date -u) between steps and stop by {until}, sooner if you run out of ideas.
6. At the end, reply to this message with the files written and a line on each, and tell Squirrel in
   chat, in a line, with no question. Then """

DREAM_ENDS = {
    "dormant": """go dormant: run lobster-mail status --as {project} --session
   <your session> dormant (it replaces dreaming) and lobster-mail pace --as {project} relaxed, run no
   watch or check-in, do not hand over, and ask Squirrel nothing until he next speaks to you: no
   question, no offer, no reminder. When he does, run lobster-mail status --as {project} --session
   <your session> --clear and lobster-mail pace --as {project} normal, start watching again as that
   prints, read the mail that arrived meanwhile, and offer to go through the dreams.
""",
    "stop": """hand over and stop: bring the record up to date, send the handover with lobster-mail
   handover (it ends the dreaming status with the duty), stop watching mail, and tell Squirrel you
   have stopped. Last of all, archive this session, so it leaves his list (in Claude Code in the
   desktop app, the archive tool with the session "self", which he approves on the card it shows;
   if you have no such tool, say so in your last line to him).
""",
}


def dream_message(project, now, minutes, then):
    """The body of the Dream message: the whole routine, so a project whose rules predate dreaming can follow it."""
    end = now + datetime.timedelta(minutes=minutes)
    fields = {"until": until(now, minutes), "minutes": minutes, "project": project, "date": f"{now:%Y-%m-%d}",
              "stamp": f"{end:%Y-%m-%dT%H:%M:%SZ}"}
    return f"Dream (from bernstein, {day(now)}).\n\n" + (DREAM_BODY + DREAM_ENDS[then]).format(**fields)


def read_conf_file(path):
    found = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                found[key.strip()] = value.strip()
    return found


def subfolders(base):
    """The folders directly inside base, by name, leaving out hidden ones."""
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    return [os.path.join(base, n) for n in names if not n.startswith(".") and os.path.isdir(os.path.join(base, n))]


def tools_folders_in(name, base):
    """(folder holding START-HERE.txt and lobster.conf, checkout) for a tools project in base, or None."""
    outer = os.path.join(base, name + "-code")
    if os.path.isdir(outer):
        return outer, os.path.join(outer, name)
    plain = os.path.join(base, name)
    return (plain, plain) if os.path.isdir(plain) else None


def non_code_folder_in(name, base):
    folder = os.path.join(base, name)
    return folder if os.path.isdir(folder) else None


def locate(name, base, found_in):
    """What found_in finds directly in base, else in the one subfolder holding it; None if none."""
    direct = found_in(name, base)
    if direct:
        return direct
    found = [f for f in (found_in(name, d) for d in subfolders(base)) if f]
    if len(found) > 1:
        places = [f[0] if isinstance(f, tuple) else f for f in found]
        count = {2: "two", 3: "three"}.get(len(places), str(len(places)))
        raise ProjectRefused(f"{name} is in {count} places, {', '.join(places[:-1])} and {places[-1]}: "
                             "keep one, or rename the other")
    return found[0] if found else None


def tools_folders(name, code_dir):
    """(folder, checkout) for a tools project in code_dir or one of its subfolders; where it would be if neither."""
    plain = os.path.join(code_dir, name)
    return locate(name, code_dir, tools_folders_in) or (plain, plain)


def find_folder(name, non_code_dir, code_dir):
    """(folder, checkout, the kind its place suggests) for a project, looking in both bases when the name does
    not say; None if it is in neither. In both: refused."""
    if name.endswith("-tools"):
        folder, checkout = tools_folders(name, code_dir)
        return (folder, checkout, "code") if os.path.isdir(folder) else None
    nc = locate(name, non_code_dir, non_code_folder_in)
    code = locate(name, code_dir, tools_folders_in)
    if nc and code:
        raise ProjectRefused(f"{name} is in two places, {nc} and {code[0]}: keep one, or rename the other")
    if nc:
        return nc, nc, "non-code"
    return (code[0], code[1], "code") if code else None


def claw_folders(claw, code_dir, conf, key):
    """(checkout, secrets folder or None) for a claw a non-code project names in lobster.conf; refused if missing."""
    outer, checkout = tools_folders(claw, code_dir)
    if not os.path.isdir(checkout):
        what = "sister tools project" if key == "SISTER" else "claw"
        raise ProjectRefused(f"the {what} {claw} is not in {code_dir} or a folder directly inside it: make it, "
                             f"or correct {key} in {conf}")
    secrets = os.path.join(os.path.dirname(outer), claw + "-secrets")
    return checkout, secrets if os.path.isdir(secrets) else None


def find_project(name, non_code_dir, code_dir):
    """Where a lobster project is, and what lobster.conf says about it."""
    found = find_folder(name, non_code_dir, code_dir)
    if found is None:
        if name.endswith("-tools"):
            raise ProjectRefused(f"no project {name} in {code_dir} or a folder directly inside it")
        raise ProjectRefused(f"no project {name} in {non_code_dir} or {code_dir}, or a folder directly inside either")
    folder, checkout, placed = found
    conf = os.path.join(folder, "lobster.conf")
    if not os.path.isfile(conf):
        raise ProjectRefused(f"{folder} has no lobster.conf: is it a lobster project?")
    try:
        settings = read_conf_file(conf)
    except UnicodeDecodeError:
        raise ProjectRefused(f"{conf} is not plain UTF-8 text: save it again as UTF-8")
    except OSError as why:
        raise ProjectRefused(f"{conf} cannot be read ({why.strerror}): check its permissions")
    kind = settings.get("KIND", placed)
    if kind not in ("code", "non-code", "feeler"):
        raise ProjectRefused(f"{conf} says KIND={kind}: it must be code, non-code or feeler")
    if not os.path.isfile(os.path.join(folder, "START-HERE.txt")):
        raise ProjectRefused(f"{folder} has no START-HERE.txt, which the session is told to follow: "
                             "bring the project into line with the lobster template first")
    for key, example in (("MODEL", "opus"), ("EFFORT", "high")):
        if not settings.get(key):
            raise ProjectRefused(f"{conf} has no {key}, which START-HERE.txt step 0 reads: "
                                 f"add a line such as {key}={example}")
    sister = settings.get("SISTER", "")
    claws = []  # (checkout, secrets folder or None), the home claw first
    claw_names = []
    if kind == "feeler":
        if sister:
            raise ProjectRefused(f"{conf} says KIND=feeler and SISTER={sister}: a feeler has no home claw; name "
                                 "the tools projects it uses in CLAWS")
        claw_names = settings.get("CLAWS", "").split()
        claws = [claw_folders(claw, code_dir, conf, "CLAWS") for claw in claw_names]
    if kind == "non-code":
        if not sister:
            raise ProjectRefused(f"{conf} has no SISTER, the tools project a non-code session works with: "
                                 f"add a line such as SISTER={name}-tools")
        claws.append(claw_folders(sister, code_dir, conf, "SISTER"))
        for claw in settings.get("CLAWS", "").split():
            claws.append(claw_folders(claw, code_dir, conf, "CLAWS"))
        claw_names = [sister] + settings.get("CLAWS", "").split()
    return SimpleNamespace(name=name, kind=kind, folder=folder, checkout=checkout, sister=sister, claws=claws,
                           claw_names=claw_names, model=settings.get("MODEL", ""),
                           effort=settings.get("EFFORT", ""))


def global_files_of(project, s, home, today):
    """The template's global files rendered for a project found by find_project; none if it names none."""
    if project.kind == "feeler":
        return globalfiles.renders(s, "feeler", project.name, "", project.folder, project.checkout, None,
                                   project.claw_names, home, today.date())
    if project.kind == "non-code":
        other = project.claws[0][0]
    else:
        try:
            other = locate(project.sister, s["NON_CODE_DIR"], non_code_folder_in) if project.sister else None
        except ProjectRefused:
            other = None
    return globalfiles.renders(s, project.kind, project.name, project.sister, project.folder, project.checkout,
                               other, project.claw_names[1:], home, today.date())


def encode(params):
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def link_for(project, mail_root, lobster_tools, name):
    """The documented desktop-app link that opens the project's session with its first line."""
    if project.kind in ("non-code", "feeler"):
        folders = [project.folder, mail_root]
        for checkout, secrets in project.claws:
            folders += [checkout] + ([secrets] if secrets else [])
        folders.append(lobster_tools)
        q = (f"Session title: {name}. Read START-HERE.txt in the {project.name} folder (mounted at ~/mnt/{project.name}) and do "
             f"what it says, starting with its step 0 before anything else. If ~/mnt/{project.name} is not "
             f"there, say \"the app opened me without the {project.name} folder\" and stop.")
        return "claude://cowork/new?" + encode([("folder", f) for f in folders] + [("q", q)])
    q = (f"Session title: {name}. This session must work in {project.folder}. If your working folder is anything else, say \"the app "
         "opened me in the wrong folder\" and stop. Otherwise read START-HERE.txt there and do what it says, "
         "starting with its step 0 before anything else.")
    return "claude://code/new?" + encode([("folder", project.folder), ("q", q)])


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="conduct", description="Start a lobster project's session, or ask a running one to "
               "hand over and stop, by mail as bernstein.",
               epilog="conduct start <project> [--brief FILE] [--pace LEVEL] [--name TEXT] [--dry-run]\n"
                      "conduct stop <project> | --all [--wait SECONDS] [--dry-run]\n"
                      "conduct finish <feeler> [--dry-run]\n"
                      "conduct dormant <project> | --all [--dry-run]\n"
                      "conduct wake <project> | --all [--dry-run]\n"
                      "conduct dream <project> | --all [--minutes N] [--then dormant|stop] [--dry-run]\n"
                      "conduct status [--json]",
               formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = p.add_subparsers(dest="verb", parser_class=Parser)
    s = verbs.add_parser("start", help="send a Start message and open the project's session")
    s.add_argument("project")
    s.add_argument("--brief", metavar="FILE", help="a file whose text is sent as the session's brief")
    s.add_argument("--pace", choices=PACES, help="set the mailbox's mail pace first")
    s.add_argument("--name", metavar="TEXT", help="what the session is called in the app's list, one line "
                   f"of at most {NAME_LIMIT} characters (default: the project and the day)")
    s.add_argument("--dry-run", action="store_true", help="show the message and the link; send and open nothing")
    t = verbs.add_parser("stop", help="ask a running session to hand over and stop")
    t.add_argument("project", nargs="?")
    t.add_argument("--all", action="store_true", help="every session on duty except bernstein's")
    t.add_argument("--wait", type=int, metavar="SECONDS", help="wait this long for the handover")
    t.add_argument("--dry-run", action="store_true", help="show the message; send nothing")
    f = verbs.add_parser("finish", help="ask a running feeler (a one-off project) to write up what it found, "
                         "propose what to do with its scripts, and hand over")
    f.add_argument("project")
    f.add_argument("--dry-run", action="store_true", help="show the message; send nothing")
    d = verbs.add_parser("dormant", help="ask a running session to stop watching mail but keep running, "
                         "with no handover, until Squirrel is back")
    d.add_argument("project", nargs="?")
    d.add_argument("--all", action="store_true", help="every session on duty except bernstein's")
    d.add_argument("--dry-run", action="store_true", help="show the message; send and set nothing")
    w = verbs.add_parser("wake", help="set a dormant session's pace back to normal and ask it to watch mail again")
    w.add_argument("project", nargs="?")
    w.add_argument("--all", action="store_true", help="every mailbox with a session on duty, fresh or stale, "
                   "except bernstein's")
    w.add_argument("--dry-run", action="store_true", help="show the message; send and set nothing")
    r = verbs.add_parser("dream", help="ask a running session to spend a while writing proposals for Squirrel, "
                         "then go dormant (or hand over)")
    r.add_argument("project", nargs="?")
    r.add_argument("--all", action="store_true", help="every session on duty except bernstein's")
    r.add_argument("--minutes", type=int, default=60, metavar="N", help="how long to dream, 5 to 240 (default 60)")
    r.add_argument("--then", choices=("dormant", "stop"), default="dormant",
                   help="what the session does after: go dormant (default) or hand over and stop")
    r.add_argument("--dry-run", action="store_true", help="show the message; send nothing")
    u = verbs.add_parser("status", help="show every mailbox's session: what it is doing, its project and its mail")
    u.add_argument("--json", action="store_true", help="print the rows as JSON")
    return p


def run(argv, env, what, stdin=None, also_fine=()):
    """Run a program; its standard output, or (exit code, detail) for an exit code in also_fine."""
    try:
        done = subprocess.run(argv, input=stdin, env=env, capture_output=True, text=True, check=False)
    except OSError as why:
        raise Stop(4, f"{what} could not be run ({why.strerror})")
    detail = (done.stderr or done.stdout).strip()
    if done.returncode in also_fine:
        return done.returncode, detail
    if done.returncode != 0:
        raise Stop(4, f"{what} failed (exit {done.returncode})" + ("\n  " + detail if detail else ""))
    return done.stdout


def listing(s, env, sleep, skipped=None):
    """The duty listing by mailbox, looking again while a duty is caught changing. The folders lobster-mail
    says it skipped are added to the list skipped, when one is given."""
    for tries in range(CHANGING_TRIES + 1):
        text = run([s["LOBSTER_MAIL"], "duty", "status", "--all", "--json", "--root", s["MAIL_ROOT"]],
                   env, "lobster-mail duty status --all")
        try:
            listed = json.loads(text)
            boxes = {m["mailbox"]: m for m in listed["mailboxes"]}
            passed_over = list(listed.get("skipped") or [])
        except (ValueError, KeyError, TypeError, AttributeError):
            raise Stop(4, "lobster-mail duty status --all --json did not print the expected JSON")
        changing = [n for n, m in boxes.items() if m.get("duty_changing")]
        if not changing:
            if skipped is not None:
                skipped.extend(passed_over)
            return boxes
        if tries == CHANGING_TRIES:
            raise Stop(4, f"the duty of {', '.join(changing)} kept changing while it was read; run conduct again")
        sleep(1)
    raise AssertionError("unreachable")  # pragma: no cover


def fresh(entry):
    duty = entry.get("duty")
    return duty is not None and not duty.get("stale")


def state_of(entry):
    """What a session is doing, from its mailbox's line in the duty listing. First match wins."""
    duty = entry.get("duty")
    if duty is None:
        return "handed-over" if entry.get("handover_waiting") else "off"
    reported = entry.get("reported") or {}
    if str(reported.get("status", "")).strip().lower() == "dormant":
        return "dormant"
    if not duty.get("stale"):
        return "running"
    return "quiet" if entry.get("pace") == "relaxed" else "stale"


SESSION_ID = re.compile(r"local_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def app_sessions(store):
    """The newest Claude Code session that is not archived, for each folder one was opened in, from the
    desktop app's own store: {real folder: {id, link, last_activity}}. The store is the app's, not ours:
    it is only read, anything in it that is not a session as expected is passed over, and a store that
    is missing or unreadable gives nothing rather than an error."""
    newest = {}
    for path in glob.glob(os.path.join(glob.escape(store), "*", "*", "local_*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            sid, cwd, last = data["sessionId"], data["cwd"], data["lastActivityAt"]
            if (data["isArchived"] is not False or not isinstance(cwd, str) or not isinstance(sid, str)
                    or not SESSION_ID.fullmatch(sid) or os.path.basename(path) != sid + ".json"
                    or isinstance(last, bool) or not isinstance(last, int)):
                continue
            when = datetime.datetime.fromtimestamp(last / 1000, datetime.timezone.utc)
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            continue
        folder = os.path.realpath(cwd)
        if folder not in newest or last > newest[folder][0]:
            newest[folder] = (last, {"id": sid, "link": "claude://claude.ai/epitaxy/" + sid, "app": "code",
                                     "last_activity": f"{when:%Y-%m-%dT%H:%M:%SZ}"})
    return {folder: found for folder, (_, found) in newest.items()}


COWORK_ID = re.compile(r"session_[A-Za-z0-9]{8,64}")


def cowork_sessions(store):
    """The newest Claude (cowork) session for each folder one was opened on, from the desktop app's own
    list: {real folder: {id, link, app, last_activity}}. The list is in the order the sessions were made
    and carries no times, so the last entry for a folder is taken as its newest and last_activity is None;
    it does not say whether a session is archived. A session belongs to the first folder connected to it.
    Only read; anything unexpected is passed over, and a missing list gives nothing rather than an error."""
    def changed(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    # with more than one list (more than one account), the one changed last is read last, so it wins
    lists = sorted(glob.glob(os.path.join(glob.escape(store), "*", "*", "remote-session-spaces.json")), key=changed)
    newest = {}
    for path in lists:
        try:
            with open(path, encoding="utf-8") as f:
                entries = json.load(f)["entries"]
            if not isinstance(entries, list):
                continue
        except (OSError, ValueError, KeyError, TypeError):
            continue
        for entry in entries:
            try:
                sid, first = entry["sessionId"], entry["folders"][0]
            except (KeyError, IndexError, TypeError):
                continue
            if isinstance(sid, str) and COWORK_ID.fullmatch(sid) and isinstance(first, str):
                newest[os.path.realpath(first)] = {"id": sid, "link": "claude://claude.ai/cowork/" + sid,
                                                   "app": "cowork", "last_activity": None}
    return newest


def status_rows(boxes, lookup, sessions=None, folder_of=None, cowork=None):
    """One row per mailbox in the duty listing, joined with what lookup(name) says of its project.
    lookup gives what find_project gives, or raises ProjectRefused as conduct start would; folder_of
    then gives the folder alone, if there is one. sessions is what app_sessions found, by folder, and
    cowork what cowork_sessions found: a non-code project gets its cowork session if it has one, any
    other row its Claude Code session, and each falls back to the other kind."""
    rows = []
    for name, entry in boxes.items():
        row = {"mailbox": name, "state": state_of(entry), "kind": None, "folder": None, "model": None,
               "effort": None, "sister": None, "claws": [], "serves": [], "refused": None,
               "duty": entry.get("duty"), "pace": entry.get("pace") or "normal",
               "new": entry.get("new", 0), "open": entry.get("open", 0),
               "handover_waiting": bool(entry.get("handover_waiting")), "reported": entry.get("reported"),
               "session": None}
        try:
            p = lookup(name)
        except ProjectRefused as why:
            row["refused"] = str(why)
            row["folder"] = folder_of(name) if folder_of else None
        else:
            row.update(kind=p.kind, folder=p.folder, model=p.model, effort=p.effort, sister=p.sister,
                       claws=list(p.claw_names))
        if row["folder"]:
            real = os.path.realpath(row["folder"])
            first, second = (cowork, sessions) if row["kind"] in ("non-code", "feeler") else (sessions, cowork)
            row["session"] = (first or {}).get(real) or (second or {}).get(real)
        rows.append(row)
    for row in rows:
        row["serves"] = [r["mailbox"] for r in rows if r["kind"] == "non-code" and row["mailbox"] in r["claws"]]
    return rows


def overdue(until_text, now):
    """Whether a reported finish time is past. One that is not lobster-mail's UTC stamp is never judged."""
    try:
        when = datetime.datetime.strptime(until_text, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return False
    return when.replace(tzinfo=datetime.timezone.utc) < now


def status_text(rows, now):
    """The rows as text, one aligned line per mailbox, in the style of lobster-mail duty status --all."""
    wide = max((len(r["mailbox"]) for r in rows), default=0)
    states = max((len(r["state"]) for r in rows), default=0)
    lines = []
    for r in rows:
        duty = r["duty"]
        who = "nobody on duty" if duty is None else (
            f"on duty {duty.get('holder')}, last beat {duty.get('last_beat')} ({duty.get('minutes')} minutes ago)")
        line = (f"{r['mailbox'].ljust(wide)}  {r['state'].ljust(states)}  {(r['kind'] or '-').ljust(8)}  {who}"
                f"  new {r['new']}  open {r['open']}  pace {r['pace']}")
        said = r["reported"]
        if said:
            line += "  reporting " + json.dumps(str(said.get("status", "")), ensure_ascii=False)
            if said.get("until"):
                line += f" until {said['until']}" + (" (overdue)" if overdue(said["until"], now) else "")
        if r["refused"]:
            line += f"  cannot start: {r['refused']}"
        lines.append(line + "\n")
    return "".join(lines)


def send(s, env, to, subject, body, err):
    """Send as bernstein. lobster-mail's exit 7 means delivered without bernstein's sent copy: it counts
    as sent, is said on standard error, and is never sent again."""
    done = run([s["LOBSTER_MAIL"], "send", "--as", "bernstein", "--to", to, "--subject", subject, "--root",
                s["MAIL_ROOT"], "-"], env, f"lobster-mail send to {to}", stdin=body, also_fine=(DELIVERED,))
    if isinstance(done, tuple):
        kind = subject.split(":")[0]
        err.write(f"conduct: the {kind} message reached {to}, but bernstein's own copy of it could not be kept "
                  f"(lobster-mail exit {DELIVERED}); it was not sent again\n  {done[1]}\n")


def start(a, s, env, today, out, err, sleep):
    if a.name is not None and name_refusal(a.name):
        raise Stop(2, f"{name_refusal(a.name)}: give --name one line of at most {NAME_LIMIT} characters")
    brief = None
    if a.brief is not None:
        try:
            with open(a.brief, encoding="utf-8") as f:
                brief = f.read()
        except OSError:
            raise Stop(2, f"the brief {a.brief} cannot be read")
    try:
        project = find_project(a.project, s["NON_CODE_DIR"], s["CODE_DIR"])
    except ProjectRefused as why:
        raise Stop(3, str(why))
    boxes = listing(s, env, sleep)
    if a.project not in boxes:
        raise Stop(3, f"there is no mailbox {a.project} in {s['MAIL_ROOT']}")
    if fresh(boxes[a.project]):
        d = boxes[a.project]["duty"]
        raise Stop(3, f"a session is already running for {a.project}: {d['holder']} has been on duty since "
                      f"{d['since']}, last beat {d['last_beat']}")
    name = session_name(a.project, today, a.name)
    try:
        rendered = global_files_of(project, s, env["HOME"], today)
    except (TemplateRefused, OSError) as why:
        raise Stop(4, f"the template cannot be read: {why}")
    split = globalfiles.is_split(rendered, project.folder)
    behind = [rel for rel, how in globalfiles.state(rendered, project.folder) if how == "behind"] if split else []
    link = link_for(project, s["MAIL_ROOT"], os.path.dirname(s["LOBSTER_MAIL"]), name)
    if a.dry_run:
        body = start_message(brief, today, name, can_rename=project.kind == "code")
        out.write(f"Would send to {a.project}, as bernstein, subject \"Start: {a.project}\":\n\n{body}\n")
        if behind:
            out.write(f"Would bring up to date in {project.folder}: {', '.join(behind)}\n")
        out.write(f"Would open:\n  {link}\n")
        out.write(f"Would name the session: {name}\n")
        out.write("Dry run: nothing was sent or opened.\n")
        return
    updated, kept = [], None
    if behind:
        try:
            updated, kept = globalfiles.bring_up_to_date(rendered, project.folder, f"{today:%Y-%m-%d-%H%M}")
        except OSError as why:
            raise Stop(4, f"a global file in {project.folder} could not be replaced ({why.strerror}): "
                          "nothing was sent or opened")
        out.write(f"Brought up to date in {project.folder}: {', '.join(updated)} (the old copies are in {kept})\n")
    elif rendered and not split:
        out.write(f"{a.project} does not keep the template's global files apart yet: its files are left as "
                  "they are.\n")
    body = start_message(brief, today, name, updated, kept, can_rename=project.kind == "code")
    if a.pace:
        pace(s, env, a.project, a.pace)
    send(s, env, a.project, f"Start: {a.project}", body, err)
    out.write(f"Sent the Start message to {a.project}.\n")
    run(["open", link], env, "open")
    out.write(f"The session is to be named: {name}\n")
    if project.kind in ("non-code", "feeler"):
        out.write(f"Opened a Claude session for {a.project}: confirm its folders, then send its first line.\n")
    else:
        out.write(f"Opened a Claude Code session for {a.project}: confirm its folder, then send its first line.\n")
        out.write(f"Ask a bernstein session in the desktop app to set its model and effort to "
                  f"{project.model}, {project.effort}.\n")


def stop(a, s, env, today, out, err, sleep):
    if a.all == (a.project is not None):
        raise Stop(2, "name one project, or give --all")
    boxes = listing(s, env, sleep)
    if a.all:
        targets = [n for n, m in boxes.items() if n != "bernstein" and fresh(m)]
        if not targets:
            out.write("Nobody is on duty anywhere but bernstein: nothing to stop.\n")
            return
    else:
        if a.project not in boxes:
            raise Stop(3, f"there is no mailbox {a.project} in {s['MAIL_ROOT']}")
        if not fresh(boxes[a.project]):
            out.write(f"Nobody is on duty for {a.project}: nothing to stop.\n")
            return
        targets = [a.project]
    body = stop_message(today)
    if a.dry_run:
        out.write(f"Would send to {', '.join(targets)}, as bernstein, subject \"Stop: hand over\":\n\n{body}\n")
        out.write("Dry run: nothing was sent.\n")
        return
    for name in targets:
        send(s, env, name, "Stop: hand over", body, err)
        out.write(f"Sent the Stop message to {name}.\n")
    if a.wait is None:
        return
    waited = 0
    while True:
        boxes = listing(s, env, sleep)
        left = [n for n in targets if boxes.get(n, {}).get("duty") is not None
                or not boxes.get(n, {}).get("handover_waiting")]
        if not left:
            for name in targets:
                out.write(f"{name} has handed over.\n")
            return
        if waited >= a.wait:
            raise Stop(5, f"after {a.wait} seconds, still on duty: {', '.join(left)}")
        sleep(WAIT_STEP)
        waited += WAIT_STEP


def finish(a, s, env, today, out, err, sleep):
    boxes = listing(s, env, sleep)
    if a.project not in boxes:
        raise Stop(3, f"there is no mailbox {a.project} in {s['MAIL_ROOT']}")
    try:
        project = find_project(a.project, s["NON_CODE_DIR"], s["CODE_DIR"])
    except ProjectRefused as why:
        raise Stop(3, str(why))
    if project.kind != "feeler":
        raise Stop(3, f"{a.project} is not a feeler: finish is for a one-off project; use stop")
    if not fresh(boxes[a.project]):
        out.write(f"Nobody is on duty for {a.project}: nothing to finish.\n")
        return
    body = finish_message(today)
    if a.dry_run:
        out.write(f"Would send to {a.project}, as bernstein, subject \"Finish: write up and hand over\":\n\n{body}\n")
        out.write("Dry run: nothing was sent.\n")
        return
    send(s, env, a.project, "Finish: write up and hand over", body, err)
    out.write(f"Sent the Finish message to {a.project}.\n")


def targets_for(a, s, env, sleep, what, stale_too=False):
    """The mailboxes a stop-like verb acts on, or None after saying there is nothing to do."""
    if a.all == (a.project is not None):
        raise Stop(2, "name one project, or give --all")
    boxes = listing(s, env, sleep)

    def on_duty(entry):
        return entry.get("duty") is not None if stale_too else fresh(entry)

    if a.all:
        found = [n for n, m in boxes.items() if n != "bernstein" and on_duty(m)]
        if not found:
            return None, f"Nobody is on duty anywhere but bernstein: nothing to {what}.\n"
        return found, None
    if a.project not in boxes:
        raise Stop(3, f"there is no mailbox {a.project} in {s['MAIL_ROOT']}")
    if not on_duty(boxes[a.project]):
        return None, f"Nobody is on duty for {a.project}: nothing to {what}.\n"
    return [a.project], None


def pace(s, env, name, level):
    run([s["LOBSTER_MAIL"], "pace", "--as", name, level, "--root", s["MAIL_ROOT"]], env, f"lobster-mail pace {level}")


def dormant(a, s, env, today, out, err, sleep):
    """Send each session on duty the Dormant message, then set its pace to relaxed."""
    found, nothing = targets_for(a, s, env, sleep, "make dormant")
    if nothing:
        out.write(nothing)
        return
    if a.dry_run:
        for name in found:
            out.write(f"Would send to {name}, as bernstein, subject \"Dormant: stop watching mail until Squirrel is "
                      f"back\":\n\n{dormant_message(name, today)}\n")
            out.write(f"Would set the pace of {name} to relaxed.\n")
        out.write("Dry run: nothing was sent or set.\n")
        return
    for name in found:
        send(s, env, name, "Dormant: stop watching mail until Squirrel is back", dormant_message(name, today), err)
        pace(s, env, name, "relaxed")
        out.write(f"Sent the Dormant message to {name} and set its pace to relaxed.\n")


def wake(a, s, env, today, out, err, sleep):
    """Set each session's pace back to normal, then send the Wake message. A dormant session's duty may be
    stale, so stale duties count too."""
    found, nothing = targets_for(a, s, env, sleep, "wake", stale_too=True)
    if nothing:
        out.write(nothing)
        return
    if a.dry_run:
        for name in found:
            out.write(f"Would set the pace of {name} to normal, then send to it, as bernstein, subject \"Wake: watch "
                      f"mail again\":\n\n{wake_message(name, today)}\n")
        out.write("Dry run: nothing was sent or set.\n")
        return
    for name in found:
        pace(s, env, name, "normal")
        send(s, env, name, "Wake: watch mail again", wake_message(name, today), err)
        out.write(f"Set the pace of {name} to normal and sent the Wake message.\n")


def dream(a, s, env, now, out, err, sleep):
    """Send each session on duty the Dream message. It sets no pace: the session goes dormant itself at the end."""
    if not 5 <= a.minutes <= 240:
        raise Stop(2, f"--minutes must be from 5 to 240, not {a.minutes}")
    found, nothing = targets_for(a, s, env, sleep, "dream")
    if nothing:
        out.write(nothing)
        return
    subject = dream_subject(now, a.minutes)
    if a.dry_run:
        for name in found:
            out.write(f"Would send to {name}, as bernstein, subject \"{subject}\":\n\n"
                      f"{dream_message(name, now, a.minutes, a.then)}\n")
        out.write("Dry run: nothing was sent.\n")
        return
    after = "dormant" if a.then == "dormant" else "hand over and stop"
    for name in found:
        send(s, env, name, subject, dream_message(name, now, a.minutes, a.then), err)
        out.write(f"Sent the Dream message to {name}: until {until(now, a.minutes)}, then {after}.\n")


def status(a, s, env, now, out, err, sleep):
    """Print what every mailbox's session is doing, joined with its project. It reads only: one duty listing
    from lobster-mail and each project's lobster.conf. Nothing is sent, set, opened or written."""
    skipped = []
    boxes = listing(s, env, sleep, skipped)
    def folder_of(name):
        """The folder of a mailbox whose project start would refuse, if it has one."""
        try:
            found = find_folder(name, s["NON_CODE_DIR"], s["CODE_DIR"])
        except ProjectRefused:
            return None
        return found[0] if found else None

    rows = status_rows(boxes, lambda name: find_project(name, s["NON_CODE_DIR"], s["CODE_DIR"]),
                       sessions=app_sessions(s["APP_SESSIONS"]), folder_of=folder_of,
                       cowork=cowork_sessions(s["APP_COWORK_SESSIONS"]))
    if a.json:
        out.write(json.dumps({"root": s["MAIL_ROOT"], "mailboxes": rows, "skipped": skipped}, indent=1) + "\n")
    elif not rows:
        out.write(f"No mailboxes in {s['MAIL_ROOT']}.\n")
    else:
        out.write(status_text(rows, now))


def main(argv, env, today, out, err, sleep):
    """Run conduct; return its exit code. today is a datetime in UTC (a dream needs the time of day)."""
    if argv[:1] in (["-h"], ["--help"]) or (len(argv) == 2 and argv[1] in ("-h", "--help")):
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
        except SettingsRefused as why:
            raise Stop(2, f"{why} (conduct --help shows the form)")
        if a.verb is None:
            raise Stop(2, "say start, stop, finish, dormant, wake, dream or status (conduct --help shows the form)")
        verbs = {"start": start, "stop": stop, "finish": finish, "dormant": dormant, "wake": wake, "dream": dream,
                 "status": status}
        verbs[a.verb](a, s, env, today, out, err, sleep)
    except Stop as stopped:
        err.write(f"conduct: {stopped.message}\n")
        return stopped.code
    return 0
