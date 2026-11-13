"""The template's global files: the ones it owns in every project's folder (PLAN.md, "Planned next", B).

A template lists them in common/global-files, one path a line, relative to a project's folder. A project
never edits one; bernstein replaces one whole when it no longer equals the template's render for that
project, keeping the old copy in the project's _to_delete/. A template without the list has none.
"""

import os

from bernstein.render import TemplateRefused

LIST = os.path.join("common", "global-files")


def declared(template_dir):
    """The global files a template names, in its order; none when it has no list."""
    path = os.path.join(template_dir, LIST)
    if not os.path.isfile(path):
        return []
    names = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if os.path.isabs(line) or line.startswith("~") or ".." in line.split("/"):
                raise TemplateRefused(f"common/global-files: {line} is not a path inside a project")
            names.append(line)
    return names


def _read(path):
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def state(rendered, folder):
    """[(path, "missing" or "behind")] for each global file the folder lacks or holds in other words."""
    found = []
    for rel, text in rendered.items():
        path = os.path.join(folder, rel)
        if not os.path.isfile(path):
            found.append((rel, "missing"))
        elif _read(path) != text:
            found.append((rel, "behind"))
    return found


def is_split(rendered, folder):
    """Whether the project keeps its global rules apart: it has every global file, current or not."""
    return bool(rendered) and all(how != "missing" for _rel, how in state(rendered, folder))


def bring_up_to_date(rendered, folder, stamp):
    """Replace each global file that is behind, whole, keeping the old copy; never touch another file.
    Returns (the paths replaced, the folder the old copies are in or None)."""
    behind = [rel for rel, how in state(rendered, folder) if how == "behind"]
    if not behind:
        return [], None
    base = os.path.join(folder, "_to_delete", f"before-global-update-{stamp}")
    kept, n = base, 1
    while os.path.lexists(kept):
        n += 1
        kept = f"{base}-{n}"
    for rel in behind:
        saved = os.path.join(kept, rel)
        os.makedirs(os.path.dirname(saved), exist_ok=True)
        os.replace(os.path.join(folder, rel), saved)
    for rel in behind:
        path = os.path.join(folder, rel)
        with open(path + ".bernstein-new", "w", encoding="utf-8", newline="") as f:
            f.write(rendered[rel])
        os.replace(path + ".bernstein-new", path)
    return behind, kept
