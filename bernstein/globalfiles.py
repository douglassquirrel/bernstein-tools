"""The template's global files: the ones it owns in every project's folder (PLAN.md, "Planned next", B).

A template lists them in common/global-files, one path a line, relative to a project's folder. A project
never edits one; bernstein replaces one whole when it no longer equals the template's render for that
project, keeping the old copy in the project's _to_delete/. A template without the list has none.
"""

import datetime
import os
import re

from bernstein.render import TemplateRefused, render_half, values_for

LIST = os.path.join("common", "global-files")
TASK_PREFIX = re.compile(r"""^task_prefix:[ \t]*["']?([A-Za-z][A-Za-z0-9]*)["']?[ \t]*(?:#.*)?\r?$""", re.MULTILINE)


class ProjectUnreadable(Exception):
    """A file of the project's own that a global file's render depends on cannot be read."""


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


def ticket_prefix(folder):
    """The prefix of a project's tickets as its own Backlog has it (task_prefix in backlog/config.yml), in
    capitals; None when the folder has no Backlog settings or they name no prefix of letters and figures.
    A project set up before the template may have chosen its own, which is the one its tickets carry."""
    path = os.path.join(folder, "backlog", "config.yml")
    if not os.path.isfile(path):
        return None
    found = TASK_PREFIX.search(_read(path))
    return found.group(1).upper() if found else None


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


def renders(s, kind, name, sister, folder, checkout, sister_path, claws, home, today):
    """{path: text} of the template's global files for one half of an existing project, rendered with
    its own names, folders, claws and ticket prefix. `sister_path` is the other half's folder (the home claw's checkout
    for a non-code project), or None when it has none or it cannot be found. Refuses a template whose
    global file would read differently on another day."""
    names = declared(s["TEMPLATE"])
    if not names:
        return {}
    non_code = kind in ("non-code", "feeler")      # the half whose own folder is the project's
    public = (not non_code) and folder != checkout
    try:
        prefix = None if kind == "feeler" else ticket_prefix(folder)     # a feeler has no tickets
    except OSError as why:
        raise ProjectUnreadable(f"{why.filename} cannot be read ({why.strerror}), so the prefix of {name}'s "
                                "tickets is not known: check its permissions")

    def on(day):
        values = values_for(name if non_code else (sister or None), kind, model=s["MODEL"], effort=s["EFFORT"],
                            non_code_dir=s["NON_CODE_DIR"], code_dir=s["CODE_DIR"], mail_root=s["MAIL_ROOT"],
                            lobster_mail=s["LOBSTER_MAIL"], public=public, today=day, home=home,
                            tools=sister if non_code else name,
                            non_code_path=folder if non_code else sister_path,
                            tools_path=sister_path if non_code else checkout, claws=claws,
                            backlog_prefix=prefix)
        rendered = render_half(s["TEMPLATE"], kind, values, public)
        return {rel: rendered[rel] for rel in names if rel in rendered}

    first, second = on(today), on(today + datetime.timedelta(days=40))
    for rel in first:
        if first[rel] != second[rel]:
            raise TemplateRefused(f"{kind}/{rel} is a global file and must read the same every day: use "
                                  "{{TEMPLATE_VERSION}} in it, not {{DATE}}")
    return first
