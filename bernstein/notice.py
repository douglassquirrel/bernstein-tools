"""notice: one notice to several projects, each with its own facts filled in (PLAN.md, Settled 162).

Everything is checked before anything is sent; one message a project goes out as bernstein, by lobster-mail.
"""


import argparse
import hashlib
import json
import os

from bernstein import conduct, facts
from bernstein.render import PLACEHOLDER
from bernstein.settings import SettingsRefused, read_settings

SENDER = "bernstein"            # as conduct sends: every project acts on mail from this mailbox
NOTHING = "nothing was sent"


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="notice", description="Send one notice to several lobster projects, as bernstein, each with "
               "its own facts filled into the same body. Everything is checked before anything is sent; a "
               "project that already has the notice unread is passed over.")
    p.add_argument("--dry-run", action="store_true", help="print every notice whole, exactly as it would be "
                   "sent; send nothing")
    p.add_argument("--subject", required=True, metavar="TEXT", help="the subject, one line, sent as given")
    p.add_argument("--body", required=True, metavar="FILE", help="the notice's text; {{PROJECT}} and {{FOLDER}} "
                   "are filled in for each project, and every other {{NAME}} from the facts file")
    p.add_argument("--facts", metavar="FILE", help="each project's own facts, as JSON: a block a project, a "
                   "name in capitals for each fact (the commands that write in projects make one with "
                   "--facts-to)")
    p.add_argument("--keep", metavar="DIR", help="write each notice as sent, with its id, into this folder")
    p.add_argument("projects", nargs="+", metavar="PROJECT", help="a project's name, which is its mailbox's")
    return p


def places(body):
    """The names of the places to fill in a body, each once, in the order they first appear."""
    return list(dict.fromkeys(PLACEHOLDER.findall(body)))


def filled(body, values):
    """The body with each place filled from values. A value is data: it is put in once, never filled itself."""
    return PLACEHOLDER.sub(lambda place: values[place.group(1)], body)


def read_text(path, what):
    """A file's text, its line endings as they are; Stop(2) if it cannot be read as UTF-8."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except UnicodeDecodeError:
        raise Stop(2, f"the {what} {path} is not plain UTF-8 text")
    except OSError as why:
        raise Stop(2, f"the {what} {path} cannot be read ({why.strerror})")


def folder_of(name, s):
    """(the project's folder, None), or (None, why it has none)."""
    try:
        found = conduct.find_folder(name, s["NON_CODE_DIR"], s["CODE_DIR"])
    except conduct.ProjectRefused as why:
        return None, str(why)
    if found is None:
        return None, (f"{name} has no folder in {s['NON_CODE_DIR']} or {s['CODE_DIR']}, or a folder directly inside "
                      "either")
    return found[0], None


def values_for(name, wanted, given, facts_path, s):
    """The value of each place the body has, for one project; Stop(3) at the first with no fact."""
    values = dict(given.get(name, {}), PROJECT=name)
    for place in wanted:
        if place == "FOLDER":
            values["FOLDER"], why = folder_of(name, s)
            if why:
                raise Stop(3, f"the body has the place {{{{FOLDER}}}}, and {why}; {NOTHING}")
        elif place not in values:
            lacks = (f"no facts file was given (--facts) to fill it for {name}" if facts_path is None else
                     f"{facts_path} has no block for {name}" if name not in given else
                     f"{facts_path} gives {name} no fact {place}")
            raise Stop(3, f"the body has the place {{{{{place}}}}}, and {lacks}; {NOTHING}")
    return values


def unread(s, env, project, subject, body):
    """The id of this very notice if it waits unread in the project's mailbox, or None: a message in its new/
    from the sender, with this subject, whose Body-SHA-256 is this body's."""
    what = f"lobster-mail list --new for {project}"
    listed = conduct.run([s["LOBSTER_MAIL"], "list", "--as", project, "--new", "--json", "--root", s["MAIL_ROOT"]],
                         env, what)
    try:
        same = [m["id"] + "" for m in json.loads(listed) if m["from"] == SENDER and m["subject"] == subject]
    except (ValueError, KeyError, TypeError, AttributeError):
        raise conduct.Stop(4, f"{what} did not print the expected JSON")
    mark = "Body-SHA-256: " + hashlib.sha256(body.encode("utf-8")).hexdigest()
    for ident in same:
        shown = conduct.run([s["LOBSTER_MAIL"], "read", "--as", project, "--root", s["MAIL_ROOT"], ident], env,
                            f"lobster-mail read {ident} for {project}")
        if mark in shown.split("\n\n", 1)[0].splitlines():
            return ident
    return None


def run(a, s, env, today, out, err, sleep):
    if "\n" in a.subject or "\r" in a.subject:
        raise Stop(2, "the subject must be one line")
    body = read_text(a.body, "body")
    given = {}
    if a.facts is not None:
        try:
            given = facts.read(read_text(a.facts, "facts file"), a.facts)
        except facts.FactsRefused as why:
            raise Stop(2, str(why))
    if a.keep is not None and not os.path.isdir(a.keep):
        raise Stop(2, f"--keep {a.keep} is not a folder: make it first")
    for name in a.projects:
        if a.projects.count(name) > 1:
            raise Stop(2, f"{name} is named twice")
    if not a.subject.strip():
        raise Stop(3, f"the subject is empty; {NOTHING}")
    if not body.strip():
        raise Stop(3, f"the body {a.body} is empty; {NOTHING}")
    for name in given:
        if name not in a.projects:
            raise Stop(3, f"{a.facts} has a block for {name}, which is not among the projects named; {NOTHING}")
    try:
        boxes = conduct.listing(s, env, sleep)
    except conduct.Stop as stopped:
        raise Stop(stopped.code, f"{stopped.message}\n  {NOTHING}")
    for name in a.projects:
        if name not in boxes:
            raise Stop(3, f"there is no mailbox {name} in {s['MAIL_ROOT']}; {NOTHING}")
    wanted = places(body)
    notices = [(name, filled(body, values_for(name, wanted, given, a.facts, s))) for name in a.projects]
    try:
        waiting = {name: unread(s, env, name, a.subject, text) for name, text in notices}
    except conduct.Stop as stopped:
        raise Stop(stopped.code, f"{stopped.message}\n  {NOTHING}")
    sent = []                                           # (project, id or None), as each goes
    for at, (name, text) in enumerate(notices):
        if waiting[name]:
            out.write(f"{name} already has this notice unread ({waiting[name]}): it is passed over.\n")
        elif a.dry_run:
            out.write(f"Would send to {name}, as {SENDER}, subject \"{a.subject}\":\n\n{text}\n")
        else:
            left = [n for n, _text in notices[at + 1:] if not waiting[n]]
            ident = send(a, s, env, name, text, sent, left, err)
            sent.append((name, ident))
            line = f"Sent to {name}: {ident or 'its id is not known'}"
            if a.keep is not None:
                try:
                    line += f" (kept as {keep(a, name, text, ident, today, sent, left)})"
                except Stop:
                    out.write(line + "\n")           # it was sent: that is said whatever became of its copy
                    raise
            out.write(line + "\n")
    had = sum(1 for name in waiting if waiting[name])
    if a.dry_run:
        out.write("Dry run: nothing was sent." + (f" Each notice sent would be kept in {a.keep}." if a.keep else "")
                  + "\n")
    elif not sent:
        out.write("Nothing was sent: every project named already has this notice unread.\n")
    else:
        also = f"; {had} project{'s' if had != 1 else ''} already had it" if had else ""
        out.write(f"Sent {len(sent)} notice{'s' if len(sent) != 1 else ''} as {SENDER}, subject \"{a.subject}\""
                  f"{also}.\n")


def named(sent):
    return ", ".join(f"{name} ({ident})" if ident else name for name, ident in sent)


def send(a, s, env, name, text, sent, left, err):
    """Send one notice; its id, or None where lobster-mail delivered it but could not say. A failure stops
    the run, saying what was sent before it and what was not attempted."""
    try:
        done = conduct.run([s["LOBSTER_MAIL"], "send", "--as", SENDER, "--to", name, "--subject", a.subject, "--root",
                            s["MAIL_ROOT"], "--json", "-"], env, f"lobster-mail send to {name}", stdin=text,
                           also_fine=(conduct.DELIVERED,))
    except conduct.Stop as stopped:
        before = f"Sent before it: {named(sent)}" if sent else "Nothing was sent before it"
        after = f" Not attempted: {', '.join(left)}." if left else ""
        raise Stop(stopped.code, f"{stopped.message}\n  {before}. Not sent: {name}.{after} Nothing is sent twice by "
                                 "naming only those not sent")
    if isinstance(done, tuple):
        err.write(f"notice: the notice reached {name}, but {SENDER}'s own copy of it could not be kept (lobster-mail "
                  f"exit {conduct.DELIVERED}); it was not sent again\n  {done[1]}\n")
        return None
    try:
        return json.loads(done)["id"] + ""
    except (ValueError, KeyError, TypeError):
        return None


def keep(a, name, text, ident, today, sent, left):
    """Write a notice as it was sent into the --keep folder, never over a file; the path it was written to."""
    path = os.path.join(a.keep, (ident or f"to-{name}-{today:%Y-%m-%d-%H%M}") + ".md")
    try:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "w", encoding="utf-8",
                       newline="") as f:
            f.write(f"From: {SENDER}\nTo: {name}\nSubject: {a.subject}\nId: {ident or 'not known'}\n\n{text}")
    except OSError as why:
        after = f" Not attempted: {', '.join(left)}." if left else ""
        raise Stop(4, f"the notice to {name} was sent ({ident or 'its id is not known'}), but its copy could not be "
                      f"kept as {path} ({why.strerror}). Sent: {', '.join(n for n, _i in sent)}.{after} Nothing is "
                      "sent twice by naming only those not attempted")
    return path


def main(argv, env, today, out, err, sleep):
    """Run notice; return its exit code. today is a datetime in UTC."""
    if "-h" in argv or "--help" in argv:
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
            run(a, s, env, today, out, err, sleep)
        except SettingsRefused as why:
            raise Stop(2, str(why))
    except Stop as stop:
        form = " (notice --help shows the form)" if stop.code == 2 else ""
        err.write(f"notice: {stop.message}{form}\n")
        return stop.code
    return 0
