"""local-history: a git repository, with no remote, for the folder around a public checkout.

PLAN.md ("A local history for the folder around a public checkout") is the specification. Exit codes: 0 done
(or a dry run), 2 bad arguments or settings or a folder that is not there, 3 refused, 5 a program it ran failed.
"""

import argparse
import json
import os
import subprocess

from bernstein.newlobster import Stop, read_conf, run_program
from bernstein.settings import SettingsRefused, read_settings

MESSAGE = "Start of this folder's local history (no remote)"
NOTHING = " Nothing was made."

# Left out of a folder's history wherever they are, by name. The top-level inbox is left out too, whole: what
# is dropped there is his original, not the folder's record, and its README.md is the template's.
LEFT_OUT_FOLDERS = (".venv", "_to_delete", "__pycache__")
LEFT_OUT_FILES = (".DS_Store",)
EXCLUDE_HEAD = ("# Left out by bernstein's local-history: the checkouts inside this folder, each by its path, "
                "and what is not this folder's record.")


def pattern_for(rel):
    """The exclude line for one folder inside, by its own path: every character of the name is data."""
    if "\n" in rel or "\r" in rel:
        raise ValueError(rel)
    escaped = "".join("\\" + c if c in "\\*?[" else c for c in rel)
    if escaped.endswith(" "):
        escaped = escaped[:-1] + "\\ "
    return "/" + escaped + "/"


def exclude_lines(nested):
    """The lines for .git/info/exclude: what is left out of the history."""
    return ([EXCLUDE_HEAD] + [pattern_for(rel) for rel in nested]
            + [name + "/" for name in LEFT_OUT_FOLDERS] + list(LEFT_OUT_FILES)
            + ["/inbox/"])


def scan(folder):
    """What is in the folder: the git repositories inside, the folders left out by name, the files kept
    (each with its size). Nothing inside a repository or a left-out folder is looked at. The folder itself
    has no .git: look() refuses one that has before this is called."""
    nested, left_out, files = [], [], []
    for here, folders, names in os.walk(folder):
        rel_here = os.path.relpath(here, folder)
        inside = "" if rel_here == "." else rel_here + "/"
        kept = []
        for name in sorted(folders):
            if os.path.lexists(os.path.join(here, name, ".git")):
                nested.append(inside + name)
            elif name in LEFT_OUT_FOLDERS or (name == "inbox" and not inside):
                left_out.append(inside + name)
            else:
                kept.append(name)
        folders[:] = kept
        for name in sorted(names):
            if name in LEFT_OUT_FILES:
                continue
            files.append((inside + name, os.lstat(os.path.join(here, name)).st_size))
    return {"nested": sorted(nested), "left_out": sorted(left_out), "files": files}


def write_exclude(repo, lines):
    """Put the lines in the new repository's .git/info/exclude, after anything git init wrote there."""
    info = os.path.join(repo, ".git", "info")
    os.makedirs(info, exist_ok=True)
    path = os.path.join(info, "exclude")
    before = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            before = f.read()
    with open(path, "a", encoding="utf-8") as f:
        f.write(("" if before.endswith("\n") or not before else "\n") + "\n".join(lines) + "\n")


class Refusing(argparse.ArgumentParser):
    def error(self, message):
        raise Stop(2, f"{message} (local-history --help shows the form)")


def parser():
    p = Refusing(prog="local-history", description=(
        "Start a git repository, with no remote, in the folder around a checkout, so that the files kept "
        "beside a public repository (rules, plan, diary) have a history of their own on this Mac. It creates "
        ".git in each FOLDER and changes no file that exists; it never adds a remote and never pushes. Left "
        "out: every git repository inside (the checkout), .venv, _to_delete, __pycache__, .DS_Store, and "
        "the top inbox."))
    p.add_argument("--dry-run", action="store_true",
                   help="check everything and say what would be committed and left out; make nothing")
    p.add_argument("folders", nargs="+", metavar="FOLDER", help="the folder around a checkout")
    return p


def repository_above(folder):
    """The nearest folder above this one that has a .git, or None."""
    here = os.path.dirname(folder)
    while True:
        if os.path.lexists(os.path.join(here, ".git")):
            return here
        up = os.path.dirname(here)
        if up == here:
            return None
        here = up


def mailbox_of(folder):
    """The mailbox the folder's lobster.conf names in SELF, or None when it has none."""
    path = os.path.join(folder, "lobster.conf")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        for line in f:
            key, _, value = line.strip().partition("=")
            if key == "SELF" and value.strip():
                return value.strip()
    return None


def duty_listing(s, env):
    """Who is on duty, by mailbox, as lobster-mail says."""
    argv = [s["LOBSTER_MAIL"], "duty", "status", "--all", "--json", "--root", s["MAIL_ROOT"]]
    what = "lobster-mail duty status --all"
    try:
        done = subprocess.run(argv, env=env, capture_output=True, text=True, check=False)
    except OSError as why:
        raise Stop(5, f"{what} could not be run ({why.strerror})")
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()
        raise Stop(5, f"{what} failed (exit {done.returncode})" + ("\n  " + detail if detail else ""))
    try:
        return {m["mailbox"]: m.get("duty") for m in json.loads(done.stdout)["mailboxes"]}
    except (ValueError, KeyError, TypeError, AttributeError):
        raise Stop(5, f"{what} --json did not print the expected JSON")


def look(folder):
    """Check one folder and say what its history would hold; stop if it must be refused."""
    if not os.path.lexists(folder):
        raise Stop(2, f"there is no folder {folder}")
    if not os.path.isdir(folder):
        raise Stop(2, f"{folder} is a file, not a folder")
    if os.path.lexists(os.path.join(folder, ".git")):
        raise Stop(3, f"{folder} already has a .git: it has a history, or is itself a checkout.{NOTHING}")
    above = repository_above(folder)
    if above:
        raise Stop(3, f"{folder} is inside the git repository at {above}: it is already in a history.{NOTHING}")
    found = scan(folder)
    if not found["nested"]:
        raise Stop(3, f"nothing inside {folder} is a git repository, so it is not the folder around a "
                      f"checkout.{NOTHING}")
    if not found["files"]:
        raise Stop(3, f"{folder} holds nothing of its own to keep: everything in it is a checkout or is left "
                      f"out.{NOTHING}")
    try:
        found["exclude"] = exclude_lines(found["nested"])
    except ValueError:
        raise Stop(3, f"{folder} cannot be given a history: a folder inside it has a line break in its name, "
                      f"which cannot be written as a line of what to leave out.{NOTHING}")
    found["mailbox"] = mailbox_of(folder)
    return found


def describe(folder, found, verb, out):
    files = found["files"]
    out.write(f"{verb} a local history in {folder}: {len(files)} files, {sum(n for _, n in files):,} bytes, "
              "no remote.\n")
    largest = sorted(files, key=lambda f: (-f[1], f[0]))[:3]
    out.write("  Largest: " + ", ".join(f"{rel} ({size:,} bytes)" for rel, size in largest) + "\n")
    left = [rel + "/ (a git repository)" for rel in found["nested"]] + [rel + "/" for rel in found["left_out"]]
    out.write("  Left out: " + ", ".join(left) + "\n")
    if found["mailbox"]:
        out.write(f"  Duty: nobody is on duty for {found['mailbox']}.\n")
    else:
        out.write("  Duty: not checked (no lobster.conf here names a mailbox).\n")


def start(folder, found, env, made):
    run_program(["git", "init", "-b", "main"], folder, env, "git init", made)
    made.append(os.path.join(folder, ".git"))
    run_program(["git", "config", "user.name", "Claude"], folder, env, "git config", made)
    run_program(["git", "config", "user.email", "claude@douglassquirrel.com"], folder, env, "git config", made)
    write_exclude(folder, found["exclude"])
    run_program(["git", "add", "-A"], folder, env, "git add", made)
    run_program(["git", "commit", "-q", "-m", MESSAGE], folder, env, "git commit", made)


def run(a, env, out):
    path, text = read_conf(env)
    try:
        s = read_settings(text, env["HOME"])
    except SettingsRefused as why:
        raise Stop(2, f"{path}: {why}")
    folders = []
    for given in a.folders:
        folder = os.path.realpath(given)
        if folder in folders:
            raise Stop(2, f"{folder} is named twice")
        folders.append(folder)
    looked = [(folder, look(folder)) for folder in folders]
    if any(found["mailbox"] for _, found in looked):
        duty = duty_listing(s, env)
        for folder, found in looked:
            holder = duty.get(found["mailbox"]) if found["mailbox"] else None
            if holder:
                raise Stop(3, f"a session is on duty for {found['mailbox']} ({holder.get('holder', '?')}): its "
                              f"folder {folder} is not changed while it works. Ask it to hand over first "
                              f"(conduct stop {found['mailbox']}).{NOTHING}")
    made = []
    for folder, found in looked:
        if not a.dry_run:
            start(folder, found, env, made)
        describe(folder, found, "Would start" if a.dry_run else "Started", out)
    if a.dry_run:
        out.write("Dry run: nothing was made.\n")


def main(argv, env, out, err):
    """Run local-history; return its exit code."""
    if "-h" in argv or "--help" in argv:
        out.write(parser().format_help())
        return 0
    try:
        run(parser().parse_args(argv), env, out)
    except Stop as stop:
        err.write(f"local-history: {stop.message}\n")
        return stop.code
    return 0
