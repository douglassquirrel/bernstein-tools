"""manifest: record every file of some projects, and afterwards say exactly what changed.

PLAN.md ("`manifest`") is the specification. Exit codes: 0 no difference (or only expected ones), 1 other
differences, 2 bad arguments or settings, 3 a project not found, 4 a file or folder could not be read.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import stat

from bernstein.conduct import ProjectRefused, find_folder
from bernstein.settings import SettingsRefused, read_settings

KINDS = ("changed", "moved", "added", "gone")


def differences(before, after):
    """What differs between two records of one folder, {path: entry} each: the paths changed, the files
    moved as (from, to), the paths added and the paths gone, each in order. A move is a file gone from one
    path and at another with the same size and checksum; files of the same bytes are paired by the same
    file name first, then in order of path. An empty file, a link or a special file is never a move."""
    changed = sorted(path for path in before if path in after and before[path] != after[path])
    gone = sorted(path for path in before if path not in after)
    added = sorted(path for path in after if path not in before)

    def bytes_of(entry):
        return (entry["sha256"], entry["size"]) if entry.get("size") else None

    waiting = {}
    for path in gone:
        if bytes_of(before[path]):
            waiting.setdefault(bytes_of(before[path]), []).append(path)
    moved = []
    for same_name in (True, False):
        for path in added:
            if path in [to for _from, to in moved]:
                continue
            for old in waiting.get(bytes_of(after[path]), []):
                if not same_name or os.path.basename(old) == os.path.basename(path):
                    moved.append((old, path))
                    waiting[bytes_of(after[path])].remove(old)
                    break
    moved.sort()
    return {"changed": changed, "moved": moved,
            "added": [path for path in added if path not in [to for _from, to in moved]],
            "gone": [path for path in gone if path not in [old for old, _to in moved]]}


def matches(path, patterns):
    """Whether a path inside a project's folder fits one of the shell patterns; * also matches /."""
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def not_expected(diff, patterns):
    """The differences that are not at a path fitting one of the patterns; a move must fit at both ends."""
    return {kind: [d for d in diff[kind]
                   if not all(matches(path, patterns) for path in (d if kind == "moved" else (d,)))]
            for kind in KINDS}


def lines(diff):
    """A line for each difference: changed, moved, added, gone."""
    return [f"{(kind + ':').ljust(8)} {' -> '.join(d) if kind == 'moved' else d}" for kind in KINDS for d in diff[kind]]


LEFT_OUT_FOLDERS = (".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache")
LEFT_OUT_FILES = (".DS_Store", ".git")
PIECE = 1 << 20
NAME = re.compile(r"[^/.][^/]*")


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def unreadable(why):
    raise Stop(4, f"{why.filename} cannot be read ({why.strerror}): check its permissions")


def record(folder):
    """{path inside the folder: entry} for every file under it: a regular file with its size and SHA-256,
    a symbolic link as a link (never followed), anything else as special. Git's, the .venv's and the
    caches' folders are left out at any depth."""
    files = {}
    for here, dirs, names in os.walk(folder, onerror=unreadable):
        inside = []
        for name in sorted(dirs):
            if name in LEFT_OUT_FOLDERS:
                continue
            if os.path.islink(os.path.join(here, name)):
                names.append(name)
            else:
                inside.append(name)
        dirs[:] = inside
        for name in sorted(n for n in names if n not in LEFT_OUT_FILES + LEFT_OUT_FOLDERS):
            path = os.path.join(here, name)
            rel = os.path.relpath(path, folder).replace(os.sep, "/")
            try:
                if os.path.islink(path):
                    files[rel] = {"link": os.readlink(path)}
                elif not stat.S_ISREG(os.lstat(path).st_mode):
                    files[rel] = {"special": True}
                else:
                    size, digest = 0, hashlib.sha256()
                    with open(path, "rb") as f:
                        while True:
                            piece = f.read(PIECE)
                            if not piece:
                                break
                            size += len(piece)
                            digest.update(piece)
                    files[rel] = {"size": size, "sha256": digest.hexdigest()}
            except OSError as why:
                unreadable(why)
    return files


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="manifest", description="Record every file of some projects with its size and checksum, "
               "and afterwards say exactly what was changed, moved, added or gone. It reads the projects and "
               "writes only the one FILE.",
               epilog="manifest save FILE PROJECT [PROJECT ...]\n"
                      "manifest compare FILE [--expect-only PATTERN]...",
               formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = p.add_subparsers(dest="verb", metavar="VERB", parser_class=Parser)
    s = verbs.add_parser("save", help="record the projects' files in FILE, a new file outside them")
    s.add_argument("file", metavar="FILE")
    s.add_argument("projects", metavar="PROJECT", nargs="+")
    c = verbs.add_parser("compare", help="read the projects again and print what differs from FILE")
    c.add_argument("file", metavar="FILE")
    c.add_argument("--expect-only", metavar="PATTERN", action="append", default=[],
                   help="exit 0 only if every difference is at a path inside its project that matches a "
                        "PATTERN (a shell pattern; * also matches /); may be given several times")
    return p


def folders_of(names, env):
    """[(name, folder)] for the projects named, found as conduct finds them."""
    path = env.get("BERNSTEIN_CONF") or os.path.join(env["HOME"], ".bernstein.conf")
    text = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    try:
        s = read_settings(text, env["HOME"])
    except SettingsRefused as why:
        raise Stop(2, f"{path}: {why}")
    found = []
    for name in names:
        try:
            place = find_folder(name, s["NON_CODE_DIR"], s["CODE_DIR"])
        except ProjectRefused as why:
            raise Stop(3, str(why))
        if place is None:
            where = (f"{s['CODE_DIR']} or a folder directly inside it" if name.endswith("-tools") else
                     f"{s['NON_CODE_DIR']} or {s['CODE_DIR']}, or a folder directly inside either")
            raise Stop(3, f"no project {name} in {where}")
        found.append((name, place[0]))
    return found


def save(a, env, now, out):
    target = os.path.abspath(a.file)
    for name in a.projects:
        if not NAME.fullmatch(name):
            raise Stop(2, f"{name!r} is not a project's name")
        if a.projects.count(name) > 1:
            raise Stop(2, f"the project {name} is named twice")
    if os.path.lexists(target):
        raise Stop(2, f"{a.file} is there already: manifest save never writes over a file; give another name, "
                      "or move it away")
    if not os.path.isdir(os.path.dirname(target)):
        raise Stop(2, f"the folder {os.path.dirname(a.file)} is not there")
    found = folders_of(a.projects, env)
    holder = os.path.realpath(os.path.dirname(target))
    for name, folder in found:
        if (holder + os.sep).startswith(os.path.realpath(folder) + os.sep):
            raise Stop(2, f"{a.file} is inside the project {name} ({folder}): keep the record outside the "
                          "projects it is of")
    projects = [{"name": name, "folder": folder, "files": record(folder)} for name, folder in found]
    data = {"manifest": 1, "saved": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "left_out": list(LEFT_OUT_FOLDERS) + [LEFT_OUT_FILES[0]], "projects": projects}
    try:
        with open(target, "x", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
            f.write("\n")
    except OSError as why:
        raise Stop(2, f"{a.file} cannot be written ({why.strerror})")
    for p in projects:
        out.write(f"{p['name']}: {counted(len(p['files']), 'file')} in {p['folder']}\n")
    out.write(f"Saved to {a.file}. Nothing else was written.\n")
    return 0


def read_record(path):
    """What manifest save wrote in a file; refused if it is anything else."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as why:
        raise Stop(2, f"{path} cannot be read ({getattr(why, 'strerror', None) or 'not UTF-8 text'})")
    try:
        data = json.loads(text)
        good = (data["manifest"] == 1 and isinstance(data["saved"], str) and isinstance(data["projects"], list)
                and all(isinstance(p["name"], str) and isinstance(p["folder"], str) and isinstance(p["files"], dict)
                        and all(isinstance(entry, dict) for entry in p["files"].values())
                        for p in data["projects"]))
    except (ValueError, KeyError, TypeError):
        good = False
    if not good:
        raise Stop(2, f"{path} is not a record that manifest save wrote")
    return data


def counted(n, one, many=None):
    return f"{n} {one if n == 1 else many or one + 's'}"


def compare(a, out):
    data = read_record(a.file)
    found = []
    for p in data["projects"]:
        if not os.path.isdir(p["folder"]):
            raise Stop(3, f"the project {p['name']} is no longer at {p['folder']}, where it was when the record "
                          "was saved")
        found.append((p, differences(p["files"], record(p["folder"]))))
    total, differing, surprises = 0, 0, []
    for p, diff in found:
        said = lines(diff)
        total += len(said)
        differing += bool(said)
        if not said:
            out.write(f"{p['name']}: no difference ({counted(len(p['files']), 'file')})\n")
            continue
        out.write(f"{p['name']}: {counted(len(said), 'difference')}\n" + "".join(f"  {line}\n" for line in said))
        surprises += [f"{p['name']}: {' '.join(line.split())}" for line in lines(not_expected(diff, a.expect_only))]
    projects = counted(len(found), "project")
    if not total:
        out.write(f"No difference in {projects} since {data['saved']}.\n")
        return 0
    out.write(f"{counted(total, 'difference')} in {differing} of {projects} since {data['saved']}.\n")
    if not a.expect_only:
        return 1
    patterns = ", ".join(a.expect_only)
    if not surprises:
        out.write(f"Every difference is at an expected path ({patterns}).\n")
        return 0
    out.write(f"Not expected (outside {patterns}):\n" + "".join(f"  {line}\n" for line in surprises))
    return 1


def main(argv, env, now, out, err):
    """Run manifest; return its exit code. now is a datetime in UTC."""
    if argv[:1] in (["-h"], ["--help"]):
        out.write(parser().format_help())
        return 0
    saving = False
    try:
        try:
            a = parser().parse_args(argv)
        except SettingsRefused as why:
            raise Stop(2, f"{why} (manifest --help shows the form)")
        if a.verb is None:
            raise Stop(2, "say save or compare (manifest --help shows the form)")
        saving = a.verb == "save"
        return save(a, env, now, out) if saving else compare(a, out)
    except Stop as stopped:
        err.write(f"manifest: {stopped.message}{'; nothing was saved' if saving else ''}\n")
        return stopped.code
