"""The lobster-mail start hook in a project's .claude/settings.json, by which a Claude Code session reads
its mail when it starts (PLAN.md, "A ganglion on the Mac: SESSION=code", step 5).

conform asks every pair for it. conduct start puts the template's file in a non-code project whose session
is a Claude Code one and whose file lacks the hook, keeping the file it replaces in the project's _to_delete/.
"""

import json
import os
import re
import shlex

REL = os.path.join(".claude", "settings.json")


def has_root(text, root):
    """Whether a hook's JSON text passes this mail root to --root, as one shell word."""
    word = json.dumps(shlex.quote(root), ensure_ascii=False)[1:-1]
    return re.search(rf' --root {re.escape(word)}(?=[\s"])', text) is not None


def has_start(text):
    """Whether a settings file's text runs lobster-mail start for the project."""
    return "lobster-mail" in text and " start --project" in text.replace('\\"', "")


def right(text, root):
    """Whether a settings file's text has the lobster-mail start hook for this mail root, whatever else it holds."""
    return has_start(text) and has_root(text, root)


class NotAFile(Exception):
    """A project's .claude/settings.json is a folder or a link; the message says which."""


def state(folder, root):
    """"missing", "right" or "wrong" for the settings file in a project's folder. NotAFile for a folder or a
    link, which is never read or replaced; OSError if the file cannot be read."""
    path = os.path.join(folder, REL)
    if os.path.islink(path):
        raise NotAFile("link")
    if not os.path.lexists(path):
        return "missing"
    if not os.path.isfile(path):
        raise NotAFile("folder")
    with open(path, encoding="utf-8", errors="replace") as f:
        return "right" if right(f.read(), root) else "wrong"


def kept_place(folder, stamp):
    """Where a settings file that is replaced goes: a folder in the project's _to_delete/ that is not there yet."""
    base = os.path.join(folder, "_to_delete", f"before-hook-{stamp}")
    kept, n = base, 1
    while os.path.lexists(kept):
        n += 1
        kept = f"{base}-{n}"
    return os.path.join(kept, REL)


def put(folder, text, kept=None):
    """Write the settings file. With kept, the file that is there is moved to that path first (its folders
    are made); without, there must be no file, and nothing is ever written over."""
    path = os.path.join(folder, REL)
    if kept:
        os.makedirs(os.path.dirname(kept))
        os.replace(path, kept)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="") as f:
        f.write(text)
