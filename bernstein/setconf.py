"""set-conf: set one setting in one lobster project's lobster.conf, guarded (PLAN.md, Settled 159).

One line of the file changes, or one is added; every other byte stays. The file as it was is kept in the
project's own _to_delete/, the new one arrives by a rename, and nothing is committed or sent.
"""

import argparse
import os
import re
import stat
from collections import namedtuple

from bernstein import conduct, facts
from bernstein.settings import SettingsRefused, check_effort, check_model, read_settings

# was, now: the line before and after, without its ending (was is None for a line that is added).
# on_lines: the numbers of the lines that set the key in the text as it was, from 1.
Change = namedtuple("Change", "text was now on_lines")

LINE = re.compile(r"([^\r\n]*)(\r\n|\r|\n|\Z)")    # a line as conduct reads one: ended by LF, CRLF or CR


def lines_of(text):
    """[(the line, its ending)] for a text; joined again they are the text, byte for byte."""
    return [m.groups() for m in LINE.finditer(text) if m.group(0)]


def sets(line, key):
    """Whether this line is the key's setting, as conduct.read_conf_file would take it."""
    return "=" in line and not line.lstrip().startswith("#") and line.split("=", 1)[0].strip() == key


def change(text, key, value):
    """The text of a lobster.conf with KEY set to VALUE, and what changed; None if nothing would."""
    lines = lines_of(text)
    on_lines = [n for n, (line, _end) in enumerate(lines, start=1) if sets(line, key)]
    if not on_lines:
        if value == "":
            return None
        end = next((end for _line, end in lines if end), "\n")
        if lines and not lines[-1][1]:
            lines[-1] = (lines[-1][0], end)
        now = f"{key}={value}"
        return Change("".join(line + e for line, e in lines) + now + end, None, now, [])
    last = on_lines[-1] - 1
    was, end = lines[last]
    if was.split("=", 1)[1].strip() == value:
        return None
    now = was[: was.index("=") + 1] + value
    lines[last] = (now, end)
    return Change("".join(line + e for line, e in lines), was, now, on_lines)


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


KEYS = ("SISTER", "CLAWS", "FOLDERS", "MODEL", "EFFORT", "SESSION")
NOTHING = "nothing was changed"


def setting(argument):
    """(KEY, VALUE) from a KEY=VALUE argument, the spaces round each dropped; Stop if it cannot be set."""
    key, equals, value = argument.partition("=")
    key = key.strip()
    if not equals or not key:
        raise Stop(2, f"{argument!r} is not KEY=VALUE: give the setting and its new value, as in "
                      "FOLDERS=~/models/voices (set-conf --help shows the form)")
    if key in ("KIND", "SELF"):
        raise Stop(3, f"KIND and SELF say what a project is, and set-conf never changes them; {NOTHING}")
    if key not in KEYS:
        raise Stop(3, f"set-conf does not know the setting {key}: it sets {', '.join(KEYS[:-1])} or {KEYS[-1]}; "
                      f"{NOTHING}")
    if "\n" in value or "\r" in value:
        raise Stop(3, f"the value for {key} has a line break in it: a setting is one line; {NOTHING}")
    return key, value.strip()


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="set-conf", description="Set one setting in one lobster project's lobster.conf: SISTER, CLAWS, "
               "FOLDERS, MODEL, EFFORT or SESSION. One line changes or is added and every other byte stays. The file as it "
               "was is kept in the project's _to_delete/. Refused while anyone is on duty for the project, and "
               "when conduct start would refuse the project with the new value. Nothing is committed or sent.")
    p.add_argument("project", metavar="PROJECT", help="a lobster project's name, as conduct takes it")
    p.add_argument("setting", metavar="KEY=VALUE", help="the setting and its new value, as in "
                   "FOLDERS=~/models/voices; an empty value (CLAWS=) is allowed")
    p.add_argument("--dry-run", action="store_true", help="show the line as it is and as it would be, and where "
                   "the file as it is would be kept; change nothing")
    p.add_argument("--facts-to", metavar="FILE", help=facts.HELP)
    return p


def kept_place(folder, stamp):
    """Where the file as it was goes: a folder in the project's _to_delete/ that does not exist yet."""
    base = os.path.join(folder, "_to_delete", f"before-conf-change-{stamp}")
    kept, n = base, 1
    while os.path.lexists(kept):
        n += 1
        kept = f"{base}-{n}"
    return os.path.join(kept, "lobster.conf")


def new_file(path, data, mode, made):
    """Write a file that must not exist yet, wholly on the disk before this returns; made gains its path as
    soon as it is this run's."""
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    made.append(path)
    with os.fdopen(handle, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(path, mode)


def write(conf, temp, kept, was, now, mode):
    """Put the new text in place of lobster.conf by a rename, the file as it was kept first. If any step
    fails, what this run made (and only that) is taken away again and lobster.conf is as it was."""
    made = []
    try:
        new_file(temp, now, mode, made)
        missing, folder = [], os.path.dirname(kept)
        while not os.path.isdir(folder):
            missing.append(folder)
            folder = os.path.dirname(folder)
        for folder in reversed(missing):
            os.mkdir(folder)
            made.append(folder)
        new_file(kept, was, mode, made)
        os.replace(temp, conf)
    except OSError as why:
        left = []
        for path in reversed(made):
            try:
                os.rmdir(path) if os.path.isdir(path) else os.remove(path)
            except OSError:
                if not os.path.isdir(path) or not os.listdir(path):
                    left.append(path)
        after = (f". Left behind, to be looked at and removed by hand: {', '.join(left)}" if left
                 else ", and nothing this run made is left")
        raise Stop(4, f"{conf} could not be changed ({why.strerror}): it is as it was{after}")


def counted(numbers):
    """1, 5 and 7"""
    return ", ".join(str(n) for n in numbers[:-1]) + f" and {numbers[-1]}"


def run(a, s, env, today, out, sleep):
    if a.facts_to and facts.refusal(a.facts_to):
        raise Stop(2, facts.refusal(a.facts_to))
    key, value = setting(a.setting)
    name = a.project
    try:
        found = conduct.find_folder(name, s["NON_CODE_DIR"], s["CODE_DIR"])
    except conduct.ProjectRefused as why:
        raise Stop(3, f"{why}; {NOTHING}")
    if found is None:
        raise Stop(3, f"no project {name} in {s['NON_CODE_DIR']} or {s['CODE_DIR']}, or a folder directly inside "
                      f"either; {NOTHING}")
    if conduct.conductor_folder(name, s["CODE_DIR"]):
        raise Stop(3, f"{name} is a conductor: its lobster.conf is its own, and is changed there by hand; {NOTHING}")
    folder = found[0]
    conf = os.path.join(folder, "lobster.conf")
    if not os.path.lexists(conf):
        raise Stop(3, f"{folder} has no lobster.conf, so it is not a lobster project whose settings can be set; "
                      f"{NOTHING}")
    if os.path.islink(conf) or not os.path.isfile(conf):
        what = "link" if os.path.islink(conf) else "folder"
        raise Stop(3, f"{conf} is a {what}, not a file: it is left alone; {NOTHING}")
    try:
        with open(conf, "rb") as f:
            was = f.read()
            mode = stat.S_IMODE(os.fstat(f.fileno()).st_mode)
    except OSError as why:
        raise Stop(3, f"{conf} cannot be read ({why.strerror}): check its permissions; {NOTHING}")
    try:
        text = was.decode("utf-8")
    except UnicodeDecodeError:
        raise Stop(3, f"{conf} is not plain UTF-8 text: save it again as UTF-8; {NOTHING}")
    changed = change(text, key, value)
    if changed is None:
        how = value if value else "empty"
        if not value and key not in conduct.conf_settings(line for line, _end in lines_of(text)):
            how = f"empty (the file has no {key} line, which reads the same)"
        out.write(f"{name}: {key} is already {how} in {conf}: nothing to change\n")
        return
    then = conduct.conf_settings(line for line, _end in lines_of(changed.text))
    try:
        conduct.checked_project(name, found, then, s["CODE_DIR"], env["HOME"])
    except conduct.ProjectRefused as why:
        raise Stop(3, f"with {key}={value} conduct start would refuse {name}: {why}; {NOTHING}")
    try:
        check_model(then["MODEL"], "MODEL")
        check_effort(then["EFFORT"], "EFFORT")
    except SettingsRefused as why:
        raise Stop(3, f"with {key}={value} the file would not do: {why}; {NOTHING}")
    try:
        boxes = conduct.listing(s, env, sleep)
    except conduct.Stop as stopped:
        raise Stop(stopped.code, f"{stopped.message}\n  {NOTHING}")
    duty = boxes.get(name, {}).get("duty")
    if duty is not None:
        raise Stop(3, f"{duty['holder']} is on duty for {name} (last beat {duty['last_beat']}): a project's files "
                      "are not changed under a session. Stop it with conduct stop, or conduct reset if it is gone; "
                      f"{NOTHING}")
    temp = conf + ".set-conf-new"
    if os.path.lexists(temp):
        raise Stop(3, f"{temp} is in the way: set-conf writes the new file there first, and never writes over "
                      f"anything. Look at it, and move it away if an earlier run left it; {NOTHING}")
    kept = kept_place(folder, f"{today:%Y-%m-%d-%H%M}")
    head = f"{name}: {conf}\n"
    if len(changed.on_lines) > 1:
        head += (f"  {key} is set on lines {counted(changed.on_lines)}: conduct reads the last, and that is the "
                 "line changed\n")
    was_line = f"(no {key} line)" if changed.was is None else changed.was
    now_line = changed.now + (" (added as the last line)" if changed.was is None else "")
    if a.dry_run:
        out.write(f"{head}  is:       {was_line}\n  would be: {now_line}\n"
                  f"  the file as it is would be kept in {kept}\n"
                  f"Dry run: nothing was changed. After the real run {name} is owed a notice by mail of the change.\n")
        if a.facts_to:
            out.write(f"The facts for a notice would be written to {a.facts_to}.\n")
        return
    write(conf, temp, kept, was, changed.text.encode("utf-8"), mode)
    out.write(f"{head}  was: {was_line}\n  now: {now_line}\n  the file as it was is kept in {kept}\n"
              f"Nothing was committed and nothing was sent: {name} is owed a notice by mail of this change.\n")
    if a.facts_to:
        why = facts.unwritten(a.facts_to, name, {"KEPT": kept, "KEY": key, "WAS": changed.was or "",
                                                 "NOW": changed.now, "WHEN": facts.when(today)})
        if why:
            raise Stop(4, why)
        out.write(f"The facts for a notice are in {a.facts_to}.\n")


def main(argv, env, today, out, err, sleep):
    """Run set-conf; return its exit code. today is a datetime in UTC, for the kept copy's name."""
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
        except SettingsRefused as why:
            raise Stop(2, f"{why} (set-conf --help shows the form)")
        run(a, s, env, today, out, sleep)
    except Stop as stop:
        err.write(f"set-conf: {stop.message}\n")
        return stop.code
    return 0
