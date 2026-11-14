"""drop-backlog: take Backlog out of a lobster project that has never used it (PLAN.md, Settled 147).

A project keeps tickets if and only if its folder has backlog/config.yml. This moves the whole backlog/
folder of a project that holds no ticket into that project's _to_delete/, so nothing is lost, and changes
nothing else there: no commit, no other file. The project's shared rules follow at its next conduct start.
"""

import argparse
import os

from bernstein import conduct
from bernstein.settings import SettingsRefused, read_settings


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="drop-backlog", description="Take Backlog out of a lobster project that has never used it: "
               "move its backlog/ folder into the project's _to_delete/. A project that holds a ticket is refused.")
    p.add_argument("projects", nargs="+", metavar="PROJECT", help="a lobster project's name")
    p.add_argument("--dry-run", action="store_true", help="say what would be moved; move nothing")
    return p


def kept_place(folder, stamp):
    """Where a project's backlog/ goes: a folder in its _to_delete/ that does not exist yet."""
    base = os.path.join(folder, "_to_delete", f"backlog-removed-{stamp}")
    kept, n = base, 1
    while os.path.lexists(kept):
        n += 1
        kept = f"{base}-{n}"
    return os.path.join(kept, "backlog")


NONE_MOVED = "nothing was moved in any project"
OWN = ("config.yml", ".DS_Store")      # what a Backlog nobody has used holds besides its empty folders


def held(backlog):
    """The files in a backlog/ folder that are not its settings, as paths inside it, in order."""
    found = []
    for here, _dirs, names in os.walk(backlog):
        found += [os.path.relpath(os.path.join(here, n), backlog) for n in names
                  if not (here == backlog and n in OWN) and n != ".DS_Store"]
    return sorted(found)


def listed(names):
    return ", ".join(names) if len(names) <= 3 else f"{', '.join(names[:3])} and {len(names) - 3} more"


def run(a, s, env, today, out, sleep):
    try:
        boxes = conduct.listing(s, env, sleep)
    except conduct.Stop as stopped:
        raise Stop(stopped.code, stopped.message)
    moving, passed_over = [], []
    for name in a.projects:
        try:
            found = conduct.find_folder(name, s["NON_CODE_DIR"], s["CODE_DIR"])
        except conduct.ProjectRefused as why:
            raise Stop(3, f"{why}; {NONE_MOVED}")
        if found is None:
            raise Stop(3, f"no project {name} in {s['NON_CODE_DIR']} or {s['CODE_DIR']}, or a folder directly "
                          f"inside either; {NONE_MOVED}")
        if conduct.conductor_folder(name, s["CODE_DIR"]):
            raise Stop(3, f"{name} is a conductor: its files are its own, and are changed there by hand; "
                          f"{NONE_MOVED}")
        folder = found[0]
        backlog = os.path.join(folder, "backlog")
        if os.path.islink(backlog) or (os.path.lexists(backlog) and not os.path.isdir(backlog)):
            raise Stop(3, f"{backlog} is a link, not a folder: it is left alone; {NONE_MOVED}")
        if not os.path.isdir(backlog):
            passed_over.append((name, folder))
            continue
        files = held(backlog)
        if files:
            count = "1 file" if len(files) == 1 else f"{len(files)} files"
            raise Stop(3, f"{name} keeps tickets: {backlog} holds {count} besides its settings ({listed(files)}). "
                          f"It is left alone, and {NONE_MOVED}")
        duty = boxes.get(name, {}).get("duty")
        if duty is not None:
            raise Stop(3, f"{duty['holder']} is on duty for {name} (last beat {duty['last_beat']}): a project's "
                          "files are not changed under a session. Stop it with conduct stop, or conduct reset if "
                          f"it is gone; {NONE_MOVED}")
        moving.append((name, backlog, kept_place(folder, f"{today:%Y-%m-%d-%H%M}")))
    for name, folder in passed_over:
        out.write(f"{name}: keeps no tickets already ({folder} has no backlog/): nothing to move\n")
    moved = []
    for name, backlog, kept in moving:
        if a.dry_run:
            out.write(f"{name}: would move {backlog} to {kept}\n")
            continue
        try:
            os.makedirs(os.path.dirname(kept))
            os.rename(backlog, kept)
        except OSError as why:
            before = f" Moved before that: {', '.join(moved)}" if moved else " Nothing was moved before that"
            raise Stop(4, f"{backlog} could not be moved to {kept} ({why.strerror}): it is where it was.{before}")
        moved.append(name)
        out.write(f"{name}: moved {backlog} to {kept}\n")
    if not moving:
        out.write("Nothing to remove.\n")
    elif a.dry_run:
        out.write("Dry run: nothing was moved.\n")
    else:
        count = "1 project" if len(moving) == 1 else f"{len(moving)} projects"
        out.write(f"Backlog removed from {count}. Nothing was committed: each project's next session commits the "
                  "removal.\n")


def main(argv, env, today, out, err, sleep):
    """Run drop-backlog; return its exit code. today is a datetime in UTC, for the kept copy's name."""
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
            raise Stop(2, f"{why} (drop-backlog --help shows the form)")
        run(a, s, env, today, out, sleep)
    except Stop as stop:
        err.write(f"drop-backlog: {stop.message}\n")
        return stop.code
    return 0
