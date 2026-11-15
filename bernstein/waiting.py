"""What is waiting across the projects, for `conduct waiting`: the facts as data and as text.

PLAN.md ("`conduct waiting`") is the specification. Everything here is a pure function of what `git` and
`lobster-mail` printed; `bernstein/conduct.py` runs them.
"""

import json
import re


def counted(n, one, many=None):
    return f"{n} {one if n == 1 else many or one + 's'}"


def repository(folder, has_git, remote="", ahead=None, status=""):
    """The facts of one repository. remote is what `git remote` printed, ahead what `git rev-list --count
    @{u}..HEAD` printed (None where the branch has no upstream; not asked where there is no remote), status
    what `git status --porcelain` printed. ValueError if ahead is not a count."""
    repo = {"folder": folder, "git": has_git, "remote": None, "upstream": None, "unpushed": None,
            "uncommitted": None, "waiting": True}
    if not has_git:
        return repo
    repo["remote"] = bool(remote.strip())
    repo["uncommitted"] = sum(1 for line in status.splitlines() if line.strip())
    if repo["remote"]:
        repo["upstream"] = ahead is not None
        if ahead is not None:
            if not re.fullmatch(r"[0-9]+", ahead.strip()):
                raise ValueError(ahead)
            repo["unpushed"] = int(ahead)
    repo["waiting"] = bool(repo["uncommitted"] or repo["unpushed"] or repo["upstream"] is False)
    return repo


def repository_line(repo):
    """One repository in a line: only what there is to say about it."""
    if not repo["git"]:
        return f"{repo['folder']}: not a git repository"
    said = []
    if not repo["remote"]:
        said.append("no remote")
    elif not repo["upstream"]:
        said.append("no upstream branch: never pushed")
    elif repo["unpushed"]:
        said.append(counted(repo["unpushed"], "commit") + " not pushed")
    if repo["uncommitted"]:
        said.append(counted(repo["uncommitted"], "file") + " uncommitted")
    elif not repo["remote"]:
        said.append("nothing uncommitted")
    return f"{repo['folder']}: " + ("; ".join(said) or "nothing waiting")


def messages(listed, state):
    """[(sender, {"id", "subject", "sent", "state"})] for what `lobster-mail list --json` printed, in its
    order. ValueError if it is not a list of messages."""
    found = []
    try:
        if not isinstance(listed, list):
            raise TypeError
        for m in listed:
            sender, entry = m["from"], {"id": m["id"], "subject": m["subject"], "sent": m["date"], "state": state}
            if not all(isinstance(v, str) for v in (sender, *entry.values())):
                raise TypeError
            found.append((sender, entry))
    except (KeyError, TypeError):
        raise ValueError("not what lobster-mail list --json prints")
    return found


def project(name, folders, mailbox, repositories, from_bernstein=(), to_bernstein=()):
    """One block of the report: a lobster project, a mailbox with no project, or a sender that is neither.
    It waits for a repository that waits or a message either way; a missing folder or mailbox is a note."""
    repositories, coming, going = list(repositories), list(from_bernstein), list(to_bernstein)
    return {"name": name, "folders": list(folders), "mailbox": mailbox, "repositories": repositories,
            "from_bernstein": coming, "to_bernstein": going,
            "waiting": bool(coming or going or any(r["waiting"] for r in repositories))}


def report(root, projects, others):
    """Everything conduct waiting says, as data."""
    projects, others = list(projects), list(others)
    repos = [r for p in projects for r in p["repositories"]] + others
    return {
        "root": root,
        "projects": projects,
        "other_repositories": others,
        "totals": {
            "projects": len(projects),
            "projects_waiting": sum(1 for p in projects if p["waiting"]),
            "other_repositories": len(others),
            "other_repositories_waiting": sum(1 for r in others if r["waiting"]),
            "commits_not_pushed": sum(r["unpushed"] or 0 for r in repos),
            "never_pushed": sum(1 for r in repos if r["upstream"] is False),
            "files_uncommitted": sum(r["uncommitted"] or 0 for r in repos),
            "not_git": sum(1 for r in repos if not r["git"]),
            "from_bernstein": sum(len(p["from_bernstein"]) for p in projects),
            "to_bernstein": sum(len(p["to_bernstein"]) for p in projects),
            "no_remote_nothing_uncommitted": sum(1 for r in repos if r["remote"] is False and not r["waiting"]),
        },
    }


STATES = {"unread": "unread", "claimed": "claimed and not closed"}


def block(p):
    """The lines of one project's block."""
    note = ""
    if not p["folders"]:
        note = " (a mailbox with no project folder)" if p["mailbox"] else " (no project folder and no mailbox)"
    elif not p["mailbox"]:
        note = " (no mailbox)"
    lines = [p["name"] + note]
    lines += ["  " + repository_line(r) for r in p["repositories"] if r["waiting"]]
    for way, key in (("From", "from_bernstein"), ("To", "to_bernstein")):
        lines += [f"  {way} bernstein, {STATES[m['state']]}: {json.dumps(m['subject'], ensure_ascii=False)}"
                  f" (sent {m['sent']})" for m in p[key]]
    return lines


def text(data):
    """The report as conduct waiting prints it: a block for each project that waits, the other repositories
    that wait, one line of totals, then how many have nothing waiting."""
    lines, t = [], data["totals"]
    for p in data["projects"]:
        if p["waiting"]:
            lines += block(p) + [""]
    others = [r for r in data["other_repositories"] if r["waiting"]]
    if others:
        lines += ["Other repositories (not lobster projects):"] + ["  " + repository_line(r) for r in others] + [""]
    if t["projects_waiting"] or t["other_repositories_waiting"]:
        said = [counted(t["commits_not_pushed"], "commit") + " not pushed",
                counted(t["files_uncommitted"], "file") + " uncommitted",
                counted(t["from_bernstein"], "message") + " from bernstein not dealt with",
                counted(t["to_bernstein"], "message") + " to bernstein not closed"]
        if t["never_pushed"]:
            said.append(counted(t["never_pushed"], "repository", "repositories") + " never pushed")
        if t["not_git"]:
            said.append(counted(t["not_git"], "folder") + " not a git repository")
        lines.append("Waiting: " + ", ".join(said) + ".")
    else:
        lines.append("Waiting: nothing.")
    lines.append("Nothing waiting in {} and {}.".format(
        counted(t["projects"] - t["projects_waiting"], "project"),
        counted(t["other_repositories"] - t["other_repositories_waiting"], "other repository",
                "other repositories")))
    if t["no_remote_nothing_uncommitted"]:
        lines.append("No remote and nothing uncommitted: {}.".format(
            counted(t["no_remote_nothing_uncommitted"], "repository", "repositories")))
    return "".join(line + "\n" for line in lines)
