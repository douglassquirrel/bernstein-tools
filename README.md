# bernstein

Tools that set up and run "lobster" projects: pairs of projects worked on with Claude, where a
non-code project does the work and asks a companion tools project, by mail, for every routine task
as a tested command. `new-lobster` makes such a pair in one step: both folders from a template,
git, a Backlog issue tracker, a mailbox each, and the first commits. `conduct` starts a project's
session and asks a running one to hand over, and `podium` shows every session on a page in your
browser, with buttons for what `conduct` does. `local-history` gives the private folder around a public
checkout a git history of its own, with no remote. They are for one person's Mac and their own
projects; the projects talk by `lobster-mail`, from the
[lobster-tools](https://github.com/douglassquirrel/lobster-tools) repository.

## Requirements

- macOS with `/usr/bin/python3` (3.9 or later) and `git`.
- Backlog, the `backlog.md` package (`backlog` on `PATH`; tested with 1.53.0).
- A checkout of `lobster-tools` for `lobster-mail`, and a mail root it can use.
- A lobster-project template: a folder with `common/`, `non-code/` and `code/`. It is not part of
  this repository; `new-lobster` reads it from the `TEMPLATE` setting. See "The template" below.

## Installation

```bash
git clone https://github.com/douglassquirrel/bernstein.git
cd bernstein
cp bernstein.conf.example ~/.bernstein.conf      # then edit what differs on your machine
./new-lobster --help
```

## Quick start

See what would be made, without making anything:

```
$ ./new-lobster --dry-run recipes
Make recipes: /Users/me/projects/non-code/recipes
Make recipes-tools: /Users/me/projects/code/recipes-tools
Then: git init -b main in each repository; backlog init in each half; lobster-mail init recipes and recipes-tools in /Users/me/projects/mail; a first commit in each; the tools' .venv.
Dry run: nothing was made.
```

Then make it:

```
$ ./new-lobster recipes
Made recipes: /Users/me/projects/non-code/recipes
Made recipes-tools: /Users/me/projects/code/recipes-tools
Mailboxes recipes and recipes-tools in /Users/me/projects/mail

GitHub is left to you. Create two repositories on github.com, empty:
  douglassquirrel/recipes (private)
  douglassquirrel/recipes-tools (private)
then push each:
  git -C /Users/me/projects/non-code/recipes remote add origin git@github.com:douglassquirrel/recipes.git
  git -C /Users/me/projects/non-code/recipes push -u origin main
  git -C /Users/me/projects/code/recipes-tools remote add origin git@github.com:douglassquirrel/recipes-tools.git
  git -C /Users/me/projects/code/recipes-tools push -u origin main

Each project's first session asks you for its purpose and brief.
```

(Real output from a run into scratch folders, with the paths shortened.)

## Usage

```
new-lobster [--dry-run] [--public] [--template DIR] [--non-code-dir DIR] [--code-dir DIR]
            [--model MODEL] [--effort EFFORT] <name>
new-lobster --claw [--dry-run] [--public] <name>
new-lobster --feeler [--dry-run] [--claws "a b"] <name>
```

- `<name>`: the non-code project's name: lower-case letters, digits and single hyphens, starting
  with a letter, 2 to 40 characters, not ending in `-tools`. The tools project is `<name>-tools`.
- `--dry-run`: check everything and render every file, print what would be made, and stop.
  Nothing is written; the only program run is the read-only mailbox listing.
- `--public`: the tools project is public. Its guidance files then stay in an outer folder,
  `<name>-tools-code/`, beside a checkout `<name>-tools/` that holds the code and an MIT licence. The outer folder also gets a git repository of its own, with no remote, started last of all with
  everything beside the checkout in it (what `local-history` does, below); a dry run says so in a line
  beginning "And:".
- `--template`, `--non-code-dir`, `--code-dir`, `--model`, `--effort`: override the settings below.

What it makes, for `recipes`: `<non-code dir>/recipes/` and `<code dir>/recipes-tools/`, each a git
repository on `main` with a first commit and Backlog (ids `RE-001` on); the mailboxes `recipes` and
`recipes-tools`; and the tools project's `.venv` with its dev tooling. It never writes over
anything, never changes the template, never deletes, and never touches GitHub.

**Ganglia and claws.** A non-code project (a *ganglion*, where the work is done) has a *home claw*, the
tools project `new-lobster` makes with it, where its new tools are born; `lobster.conf` names it as
`SISTER`. It may also use further claws, other tools projects, named in a `CLAWS=word-tools
google-docs-tools` line. A claw that serves any project and has no non-code half of its own is a
*lone claw*: `KIND=code` and an empty `SISTER` in its `lobster.conf`.

**Making a lone claw.** `new-lobster --claw [--public] [--dry-run] <name>` makes one tools project
on its own: its folder (the public layout with `--public`), a git repository with a first commit,
Backlog, one mailbox and the `.venv`, and prints the commands for its one GitHub repository. The
name may end in `-tools`. Its first session asks you which projects will use it.

**Bringing an existing pair, or an existing claw, into line.** `new-lobster --render-into DIR [--tools NAME]
[--claws "NAME NAME"] [--non-code-path DIR] [--tools-path DIR] [--public] [--dry-run] <name>` renders the
template for a pair that already exists, with its own names, folders and further claws, into
`DIR/non-code/` and `DIR/code/` (the code half in one folder, even when public), for you to merge by
hand. `new-lobster --render-into DIR --claw [--tools-path DIR] [--public] <name>` renders the code half
only, for a lone claw. Either writes nothing else: no project folder, repository, Backlog or mailbox,
and runs no program. `--tools` is the home claw's name (default `<name>-tools`; it must end in `-tools`);
the paths default to where `new-lobster` would put the pair. `DIR` must not exist (exit 3). With
`--dry-run` it lists the files and writes nothing. `--tools`, `--claws`, `--non-code-path` and
`--tools-path` need `--render-into`, and `--tools`, `--claws` and `--non-code-path` cannot go with
`--claw` (exit 2). For example:

```
new-lobster --render-into /tmp/tv --tools training-video-tools --public \
    --non-code-path ~/projects/non-code/videos/training-video \
    --tools-path ~/projects/code/videos/training-video-tools-code/training-video-tools training-video
new-lobster --render-into /tmp/ba --tools book-tools --claws "word-tools google-docs-tools" \
    --non-code-path ~/projects/non-code/writing/beyond-ai \
    --tools-path ~/projects/code/writing/book-tools-code/book-tools beyond-ai
new-lobster --render-into /tmp/wt --claw --public \
    --tools-path ~/projects/code/writing/word-tools-code/word-tools word-tools
```

### Settings

`~/.bernstein.conf` (or the file named by `BERNSTEIN_CONF`): `KEY=value` lines, `#` comments,
optional quotes, `~` for your home folder. All optional; `bernstein.conf.example` lists them:

| Setting | Default | Flag |
|---|---|---|
| `TEMPLATE` | `~/projects/code/bernstein-code/templates/lobster` | `--template` |
| `NON_CODE_DIR` | `~/projects/non-code` | `--non-code-dir` |
| `CODE_DIR` | `~/projects/code` | `--code-dir` |
| `MODEL` | `opus` | `--model` |
| `EFFORT` | `high` (`low`, `medium`, `high`, `xhigh` or `max`) | `--effort` |
| `LOBSTER_MAIL` | `~/projects/code/lobster-tools-code/lobster-tools/lobster-mail` | |
| `MAIL_ROOT` | `~/projects/mail` | |
| `PYTHON` | `/usr/bin/python3` | |

### The template

A folder with `common/sections/` (text shared by both halves), `common/inbox/README.md`,
`common/lobster.conf`, and the two halves' own files in `non-code/` and `code/`. In any file, a line
that is exactly `{{> sections/<file>.md}}` is replaced by that file from `common/sections/` (the
name may contain `{{VISIBILITY}}`), and a placeholder whose name is only capital letters and
underscores, such as `{{NAME}}`, `{{TOOLS}}`, `{{SELF}}`, `{{SISTER}}`, `{{DATE}}`, `{{MODEL}}` or
`{{EFFORT}}`, is filled in; an unknown one is an error. Any other `{{…}}` is left as written, for
the project's first session to complete.

**Global files.** A template may own some files in every project's folder: the rules and routines
that are the same everywhere, kept apart from what a project writes for itself. It names them in
`common/global-files`, one path a line relative to a project's folder (`#` starts a comment), for
example:

```
LOBSTER-RULES.md
START-HERE.txt
inbox/README.md
```

A global file must read the same every day, so it may not use `{{DATE}}`; `{{TEMPLATE_VERSION}}`
is the line in `common/version` (empty when there is none). A project never edits a global file.
`conform` lists one that is missing or no longer equals the template's render for that project's
own names, folders and claws, and `conduct start` replaces any that are behind (below).
**Ticket ids.** In a global file `{{BACKLOG_PREFIX}}` is the prefix the project's own tickets carry:
`task_prefix` in its `backlog/config.yml`, in capitals, when that names one of letters and figures.
Only a project with no such setting gets the prefix worked out from its name (the first two letters),
which is also what `new-lobster` gives a new project. The settings file is only read; if it is there
but cannot be read, `conduct start` stops with exit 3 and `conform` with exit 4, naming the file, and
nothing is changed. A feeler has no tickets, so nothing is read for one. In a
public tools project a global file sits beside the checkout, like `CLAUDE.md`, and is never
committed in it. A template without the list has no global files, and nothing below changes.

## Feelers: light projects for one-off work

A *feeler* is a lobster project for work that will not be run over and over: looking something up,
extracting something once, a single piece of analysis. It is one folder under the non-code tree with
a short CLAUDE.md for what it is for and what was found, the template's few shared rules for
feelers (`LOBSTER-RULES.md`), a short `START-HERE.txt`, a diary, a git repository and a mailbox. It
has no tools project of its own, no Backlog, no inbox and no check-in chain: its mail pace is
`relaxed` from the start.

```
$ ./new-lobster --feeler --dry-run literary-agents
Make the feeler literary-agents: /Users/sq/projects/non-code/literary-agents
Then: git init -b main; lobster-mail init literary-agents in /Users/sq/projects/mail, pace relaxed; a first commit.
Dry run: nothing was made.
```

- `--claws "word-tools google-docs-tools"` names the claws it uses (`CLAWS` in its `lobster.conf`,
  which you may change later); `conduct start` connects each to its session, and a claw that is not
  there is exit 3. A feeler may ask a claw for a tool or a fix by mail, as any project does.
- Unlike a project that runs again and again, a feeler may write scripts; each is kept in its
  `tools/`, and `conduct finish` asks what should become of them.
- `conduct start`, `stop`, `status`, `dormant`, `wake` and `dream` treat it like any project; it
  opens as a Claude session with its folder, the mail root, its claws and `lobster-tools`.
- `conform <feeler>` checks it alone: `lobster.conf` (KIND=feeler, an empty SISTER, MODEL, EFFORT),
  `START-HERE.txt`, `CLAUDE.md`, its claws, the template's global files, a git repository and the
  mailbox; it ends "The feeler is in line."
- `--claw`, `--public` and `--tools` are refused with `--feeler` (exit 2), and a name ending in
  `-tools` is refused. `--render-into DIR` renders a feeler's files only, for making an existing
  one-off folder a feeler by hand. The template's feeler files are in its `feeler/` folder.

## conduct: starting and stopping a project's session

```
conduct start   <project> [--brief FILE] [--pace eager|normal|relaxed] [--name TEXT] [--again] [--dry-run]
conduct stop    <project> | --all  [--wait SECONDS] [--dry-run]
conduct finish  <feeler>  [--dry-run]
conduct dormant <project> | --all  [--dry-run]
conduct wake    <project> | --all  [--dry-run]
conduct dream   <project> | --all  [--minutes N] [--then dormant|stop] [--dry-run]
conduct status  [--json]
```

`conduct` talks to a lobster project's session by mail, as `bernstein`; each project's guidance
says to act on bernstein's mail at once (since 8 November 2026, apart from a request for a tool,
which waits for Squirrel's OK). It reads who is on duty with `lobster-mail duty status
--all` and, at a start, the project's unread mail with `lobster-mail check`, and writes in a project's folder only to bring the template's global files up to date
at a start (below).

- **`start`** refuses if a session is already on duty for the project. It also refuses while a Start
  it sent less than ten minutes ago still waits unread in the project's mailbox, since that session is
  probably still opening and a second Start would only open a second one: the message gives the time
  the first was sent and when the ten minutes end, and `--dry-run` refuses the same way. If no session
  came of the first (the app's form was closed, or the session opened in the wrong folder), wait for
  that time or add `--again`, which sends another at once. Otherwise it sets the mail
  pace if `--pace` is given, mails a Start message (follow `START-HERE.txt` from the top, clear any
  status an earlier session left reported for the mailbox, name the session, then the brief from
  `--brief FILE`, or wait), and opens the session in the Claude desktop app with the
  documented link: a Claude session for a non-code project, with its folder, the mail root, its
  home claw, each further claw in `CLAWS`, each claw's `<claw>-secrets` folder when there is one
  beside it, and `lobster-tools` connected; a Claude Code session for a tools project. You
  confirm the folders and send the prefilled first line. For a Claude Code session it reminds you
  to have a bernstein session set its model and effort, which a program cannot do.
  **Global files.** If the template names global files and the project has them all, `start`
  replaces each one that no longer equals the template's render, whole, before it sends anything:
  the old copy goes to the project's `_to_delete/before-global-update-<date>-<time>/`, the Start
  message tells the session which files changed and asks it to commit them, and `--dry-run` prints
  "Would bring up to date in …" and writes nothing. No other file is touched, and a start that is
  refused touches none. A project that lacks one of the global files does not keep them apart yet:
  it is left exactly as it is, and `start` says so. If an old copy cannot be kept, nothing is
  replaced, sent or opened (exit 4).
  **The session's name** is the project and the day ("recipes-tools · 18 October"), or `--name TEXT`
  (one line, at most 60 characters; an empty, two-line or longer name is exit 2). A program cannot
  rename a session in the app, so the name travels two ways. The prefilled first line begins
  "Session title: <name>.", since the app titles a new session from its first message (it writes its
  own summary, so this steers the title rather than setting it). And the Start message asks a Claude
  Code session to give itself exactly that title with the app's tool for naming a session; a Claude
  Cowork session (a non-code project or a feeler) has no such tool, so it is only told its name.
  `--dry-run` prints "Would name the session: …". podium's Start dialog has a field for the name.
- **`finish`** is for a feeler (below): it mails a running feeler a Finish message asking it to write up
  what it found in its CLAUDE.md, list every script in its `tools/` with a proposal for each (offer it
  to a claw by mail, on your OK, or leave it as a record), bring its state up to date, commit, hand
  over, reply with what was found, and archive its session. With nobody on duty it sends nothing
  (exit 0); a project that is not a feeler is exit 3 ("use stop"). You move the folder to
  `not-current/` yourself when you have read the reply.
- **`stop`** mails a Stop message: hand over at the next safe point, then stop, and last of all archive
  the session so that it leaves your list (in Claude Code in the desktop app the session does this with
  the app's archive tool, which you approve on a card; a session with no such tool says so instead). `--all` asks every
  session on duty except bernstein's. `--wait SECONDS` waits for each handover, looking every 10
  seconds.
- **`dormant`** puts a running session to sleep without a handover, for a pause such as overnight:
  it mails a Dormant message (keep running, keep everything as it is, do not hand over, report
  `dormant` with `lobster-mail status`, stop watching mail and run no mail checks; when Squirrel next
  speaks to you, clear that status, set the pace back to normal and watch again; until then, ask
  Squirrel nothing) and then sets the mailbox's pace to `relaxed`, at which a session reads mail only at
  the end of a turn. Only sessions fresh on duty; `--all` is every one but bernstein's. The session's
  duty goes stale after 45 minutes; `conduct status` shows it as `dormant` from the moment it reports so.
- **`wake`** is the way back when Squirrel would rather not speak to each session: it sets the pace to
  `normal` and mails a Wake message (clear the `dormant` status, watch mail again, read what arrived,
  carry on). A dormant
  session reads it at the end of its next turn, so it takes effect when the session is next used;
  stale duties count, since a dormant session's does go stale.
- **`dream`** asks a running session to spend a while, 60 minutes unless `--minutes` says otherwise (5 to
  240), looking back over its recent work and writing proposals for Squirrel: rules to merge so that less
  has to be read at startup, repeated actions to make into tools, and any other idea, one file per topic
  in the project's `dreams/`, changing nothing else. The Dream message carries the whole routine, with the
  finish time in UTC (the subject is `Dream: until HH:MM UTC`). While dreaming the session watches for
  bernstein's mail only (`lobster-mail wait --from bernstein`) and leaves the rest unclaimed, and it
  reports `dreaming` with the finish time (`lobster-mail status … dreaming --until …`), which `conduct
  status` shows; going dormant at the end it reports `dormant` instead, and a handover ends the status. At the end
  it replies, tells Squirrel in a line with no question, and goes dormant, asking nothing until he next
  speaks to it; or with `--then stop` hands over and stops. `conduct` sets no pace for a
  dream. Only sessions fresh on duty; `--all` is every one but bernstein's.
- **`--dry-run`** shows the message and the link, and sends and opens nothing (for `dormant` and
  `wake`, sets nothing either).
- **`status`** shows every mailbox under the mail root, one line each: what its session is doing, the
  project's kind, who is on duty and when it last checked in, the mail waiting (`new`) and claimed
  (`open`), the pace, the status the session reports about itself if it has set one (`lobster-mail
  status`; marked `(overdue)` once its finish time has passed), and, where `start` would refuse the
  project, why. It reads one duty listing and each project's `lobster.conf`; it sends, sets, opens and
  writes nothing, so it has no `--dry-run`.

  ```
  $ ./conduct status
  recipes        running      non-code  on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)  new 2  open 0  pace normal  reporting "dreaming" until 2026-10-18T10:20:00Z
  recipes-tools  handed-over  code      nobody on duty  new 0  open 0  pace normal
  video-tools    quiet        code      on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)  new 0  open 0  pace relaxed
  ```

  The second word is the state, the first of these that fits:

  | State | When |
  |---|---|
  | `dormant` | a session is on duty and has reported `dormant` |
  | `running` | a session is on duty and has checked in within 45 minutes, at any pace |
  | `quiet` | on duty at pace relaxed with no check-in for 45 minutes: waiting to be spoken to, or gone |
  | `stale` | on duty at any other pace with no check-in for 45 minutes: it probably died, or the Mac slept |
  | `handed-over` | nobody on duty, and the last session's handover is waiting for the next |
  | `off` | nobody on duty |

  `--json` prints `root`, `skipped` (as `lobster-mail` gives them) and `mailboxes`, each with `mailbox`,
  `state`, `kind` (`non-code`, `code`, or `null` when the project cannot be read), `folder`, `model`,
  `effort`, `sister`, `claws` (for a non-code project, the tools projects it works with, its sister
  first), `serves` (for a tools project, the non-code projects that name it), `refused` (why `start`
  would refuse, or `null`), `session` (below), and `duty`, `pace`, `new`, `open`, `handover_waiting` and
  `reported` as `lobster-mail duty status --all --json` gives them. `reported` needs a `lobster-tools` with the
  `status` verb (10 November 2026); with an older one it is always `null`.

`start` checks the project before it sends or opens anything, and refuses (exit 3) with a message
saying what to fix when any part a lobster project has is missing: the folder (`<CODE_DIR>/<name>`
or `<CODE_DIR>/<name>-code` for a name ending `-tools`; for any other name, `<NON_CODE_DIR>/<name>`
or, failing that, `<CODE_DIR>/<name>` or `<CODE_DIR>/<name>-code`, so a claw such as `transcriber`
is found and its kind read from `lobster.conf`; each may be one level down, in a subfolder that
keeps related projects together, such as `~/projects/code/videos/`; one directly in the folder
wins, and the same name in two places is refused), a `lobster.conf` it can read as UTF-8 text, a
KIND of `code` or `non-code`, `START-HERE.txt`, MODEL and EFFORT lines, and, for a non-code
project, a SISTER line naming a tools project that exists and a CLAWS line naming only ones that
do.
A project made before the lobster template needs these before `conduct` can start it.

If `lobster-mail` reports exit 7 (the message was delivered, but bernstein's own copy in `sent/`
could not be written), `conduct` counts the message as sent: it says so on standard error, never
sends it again, and carries on (opening the session, or waiting for the handover).

A session sees mail at its own pace: at once when eager, at the next pause when normal, only at
the end of a turn when relaxed. So a Stop to a relaxed session waits until you next talk to it.

| Code | Meaning |
|---|---|
| 0 | Sent (and, with `--wait`, handed over); or, for `stop`, `dormant`, `wake` and `dream`, nobody on duty; or, for `status`, shown |
| 2 | Bad arguments or settings, or `--minutes` outside 5 to 240 |
| 3 | No such project or mailbox, or the project lacks a part `start` needs; or, for `start`, a session is already on duty, or a Start sent in the last ten minutes still waits unread |
| 4 | A program failed, or the duty listing or the project's list of new mail could not be read |
| 5 | `--wait` ran out before the handover arrived |

  `session` is the project's newest session in the Claude desktop app: `{"id", "link", "app",
  "last_activity"}`, or `null` when there is none. The link opens that session in the app. `app` says
  which kind it is:
  - `code`: a Claude Code session whose folder is the project's, the newest that is not archived
    (`claude://claude.ai/epitaxy/<id>`), with when it was last active. Read from the app's session files
    (the setting `APP_SESSIONS`, `~/Library/Application Support/Claude/claude-code-sessions` unless set).
  - `cowork`: a Claude session whose first connected folder is the project's
    (`claude://claude.ai/cowork/<id>`). Read from the app's list of those sessions (the setting
    `APP_COWORK_SESSIONS`, `~/Library/Application Support/Claude/local-agent-mode-sessions` unless set).
    That list is in the order the sessions were made and has no times, so the last one listed for the
    folder is taken as the newest, `last_activity` is `null`, and it may be one you have archived.

  A non-code project gets its `cowork` session if it has one, any other its `code` session, and each
  falls back to the other kind. `conduct` only reads these files, never writes them. They are the app's
  own and undocumented, so if they are missing or change shape every `session` is simply `null`. The
  text form does not show it.

## podium: a page showing every session, with buttons

```
podium [--port N] [--no-open]
```

`podium` shows what `conduct status` shows, as a page in your browser: one card for each non-code
project with the tools projects it works with under it (its sister as "home claw", the rest as "claw"),
then the tools projects that serve no one ("lone claws"), then mailboxes whose project `conduct` could
not start, each with the reason, then bernstein's own. Each line has the session's state as a coloured
badge, the kind of session on duty and how long ago it checked in ("Claude Code" for a session on the Mac,
whose mail name is `mac`; "Claude Cowork" for one in the app's virtual machine, whose mail name is `device`),
and the project's model and effort; the pace is
shown only when it is not normal, and mail waiting or claimed only when there is some. A running session that reports a status shows that in the badge (`dreaming
until 10:20 UTC`), and `overdue since` once its finish time has passed. The page makes itself again
every 15 seconds and when you press Refresh, follows your light or dark setting, and works at the
width of a phone. It is set in EB Garamond if that typeface is installed on the Mac, and in Georgia if
not; nothing is fetched from anywhere, so no font is downloaded.

A line whose project has a session in the desktop app starts its buttons with **Open**, a link that takes
you straight to the newest one: a non-code project's Claude session, or a tools project's Claude Code
session (your browser may ask once whether the page may open Claude). It is there for bernstein's own line
too.

Each line has buttons for what can be done to that session now: **Start** when nobody is on duty and
`conduct` could start the project; **Stop**, **Dormant** and **Dream** when it is running; **Wake** when
it is dormant, quiet or stale. A bar at the top has **Stop all**, **Dormant all**, **Dream all** and
**Wake all** when any session but bernstein's is in that state; bernstein's own line has no buttons.
Nothing happens at one press:

1. The button opens a dialog. Start asks for an optional brief (sent word for word) and mail pace; Dream
   for the minutes (5 to 240) and what comes after; Stop asks "Dream first?" (yes makes it a dream that
   ends in a handover) and for an optional wait for the handover (1 to 600 seconds).
2. **Preview** runs the `conduct` command with `--dry-run` and shows the command and everything it
   printed: the message that would be sent, word for word. If `conduct` would refuse, its reason is
   shown and there is nothing to send.
3. **Send** runs exactly what was previewed, once, and shows what `conduct` printed and its exit code.
   After a Start it reminds you what only you can do in the desktop app. Cancel sends nothing.

While `conduct` is running, for a preview or a send, the dialog says what it is waiting for and counts
the seconds ("Sending: conduct stop recipes… 4 s"); `conduct`'s own output appears when it has finished.

What podium has run since it started is listed under "Activity" at the foot of the page, and each run
is added to a log file (the setting `PODIUM_LOG`, `~/.bernstein/podium.log` unless set; its folder is
made if missing): the time, the command, the exit code and the output. A preview is not a run and is
not logged.

```
$ ./podium
podium is serving at http://127.0.0.1:8417/?t=<a fresh token each run>
It runs only while this command runs: stop it with Ctrl-C.
```

- It is a small web server on this machine only (`127.0.0.1`), for as long as the command runs in
  your Terminal: Ctrl-C or closing the window stops it. Nothing starts at login and nothing is left
  running.
- Every address needs the token in the link, which is new each run, so no other page in your browser
  and no other program can read it without the link. Without the token the answer is 403.
- It only ever runs `conduct` (the one beside it): `conduct status --json` each time the page is made,
  and the verb you previewed and sent, as a list of arguments, never through a shell. It never runs
  `lobster-mail` itself, so every refusal and every message is `conduct`'s own.
- It writes only two things: the log, added to and never written over, and a brief you typed, as a
  temporary file while `conduct` reads it, removed straight afterwards.
- It acts only on a mailbox in the listing it last showed, only with the verbs and options above, only
  one action at a time (a second while one runs is told "busy"), and only the latest preview can be
  sent, once.
- `--port N` (or the setting `PODIUM_PORT`, 8417 unless set; 0 for any free port) says where to serve.
  If that port is in use, a free one is used and podium says so.
- `--no-open` prints the link without opening the browser. If the browser cannot be opened, podium
  says so and serves all the same.
- If `conduct status` fails, the page shows its message in place of the cards and tries again at the
  next refresh; if podium itself has stopped, the page says so.
- Addresses: `/` the page, `/view` the part that is made again, `/status` what `conduct status --json`
  printed (502 with the reason when it failed), each answering GET with `?t=<token>`. The buttons POST
  JSON to `/preview` (`{"t": token, "action": {…}}`) and `/run` (`{"t": token, "ticket": …}`).

| Code | Meaning |
|---|---|
| 0 | Stopped (Ctrl-C), having served |
| 2 | Bad arguments or settings |
| 4 | It could not start serving (the message says why) |

## conform: what an existing pair or claw lacks

```
conform <non-code> <home claw>
conform <lone claw>
```

`conform` reads an existing pair and lists, half by half, what it lacks against the template; it
changes nothing. With one name it checks a lone claw alone, as a code half with an empty SISTER,
and ends "The claw is in line." In a pair's check, a home claw whose `lobster.conf` has an empty
SISTER is a lone claw serving this project among others, and is checked as one. It finds each half
where `conduct` looks (one subfolder down included), then checks: `lobster.conf` (readable, with the right KIND, SELF and SISTER and a MODEL
and EFFORT), for a non-code project every claw in CLAWS present in the code folder, `START-HERE.txt`,
`.claude/settings.json` with the `lobster-mail start` hook passing this mail root to `--root`,
`inbox/README.md`, CLAUDE.md having each section the template's CLAUDE.md for that half takes from
`common/sections/` and each heading naming the pair, the Inbox and Mail sections in the template's
exact wording (blank lines aside), a git repository, `backlog/`, the mailbox, and, for a public tools
project, none of the outer files (CLAUDE.md, PLAN.md, DIARY.md, START-HERE.txt, `lobster.conf`,
`inbox/`, `.claude/`, and the template's global files) inside the checkout. When the template names
global files, each must be in the project's folder and equal the template's render for that project:
one that is absent is `missing: <file>, one of the template's global files`, and one in other words
is `missing: the template's current <file> (a global file: conduct start brings it up to date)`. The
render uses the ticket prefix in the project's own `backlog/config.yml` when it has one. A
template whose global file would read differently on another day is exit 4. For example, for a
pair brought into line:

```
$ ./conform training-video training-video-tools
training-video (non-code): /Users/sq/projects/non-code/videos/training-video
  in line
training-video-tools (code): /Users/sq/projects/code/videos/training-video-tools-code
  in line
Both halves are in line.
```

A gap is a line `missing: …`; a half that cannot be found, or is in two places, says so. Exit codes:
0 nothing missing, 1 something missing, 2 bad arguments or settings, 4 the template, or a project's `backlog/config.yml`, cannot be read.
Use it with `new-lobster --render-into` to bring an older pair into line.

## local-history: a history for the folder around a public checkout

```
local-history [--dry-run] FOLDER [FOLDER ...]
```

A public tools project keeps its rules, plan and diary in the folder around the checkout, so that they
are not in the public history. That leaves them in no history at all. `local-history` makes a git
repository in that outer folder, with no remote, and commits what is there once, so that a file
emptied or written over by mistake comes back with `git checkout -- <file>`. The repository is on the
same disk as the files: it is not a backup.

It creates `.git` in each folder and changes no file that exists (it writes no `.gitignore`: what is
left out goes in the new `.git/info/exclude`). It never adds a remote and never pushes. Left out of
the history: every git repository inside the folder, by its path (the checkout); `.venv/`,
`_to_delete/`, `__pycache__/` and `.DS_Store` wherever they are; and the top-level `inbox/`.

Run it with `--dry-run` first. It checks every folder and says what would be committed and left out,
running no git:

```
$ ./local-history --dry-run ~/projects/code/demo-tool-code
Would start a local history in /Users/sq/projects/code/demo-tool-code: 4 files, 93 bytes, no remote.
  Largest: lobster.conf (56 bytes), DIARY.md (29 bytes), CLAUDE.md (6 bytes)
  Left out: demo-tool/ (a git repository), .venv/, _to_delete/, inbox/, tools/__pycache__/
  Duty: nobody is on duty for demo-tool.
Dry run: nothing was made.
```

The count is by this command's own rules; a `.gitignore` already in the folder may leave out more.
Without `--dry-run` the same lines begin "Started a local history in", and afterwards `git status
--short` in the folder prints nothing and `git remote` prints nothing.

It refuses, making nothing in any of the folders named, when one of them: is not there or is a file
(exit 2); is named twice (2); already has a `.git` (3); is inside a git repository (3); has no git
repository inside it, so is not the folder around a checkout (3); holds nothing of its own to keep
(3); has a folder inside whose name contains a line break (3); or belongs to a project whose session
is on duty, fresh or stale (3): the project is the one its `lobster.conf` names in `SELF`, and a
folder with no `lobster.conf` is not checked ("Duty: not checked"). If `git` or `lobster-mail` fails or
cannot be run, it stops with exit 5 and that program's own words, and says which `.git` folders it had
already made; those are left as they are.

Afterwards, commit in the outer folder whenever its files are worth keeping (`git add -A && git
commit -m "..."`, run in the outer folder, not the checkout).

## Errors and exit codes

Every failure is one line on standard error starting `new-lobster:`, saying what happened. (`conduct`,
`conform` and `local-history` give their own codes in their sections above.)

| Code | Meaning | What to do |
|---|---|---|
| 0 | Done, or a dry run | |
| 2 | A bad name, flag or settings line | The message names the rule or the line; `--help` shows the form |
| 3 | A folder or a mailbox it would make already exists | Choose another name, or move the existing one yourself |
| 4 | The template cannot be used (missing, a missing include, an unknown placeholder) | Fix the template; nothing was written |
| 5 | A program it runs failed (`git`, `backlog`, `lobster-mail`, Python) | The message says what failed and lists what was already made, which is left as it is |

## Testing

```bash
/usr/bin/python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest            # all tests, with coverage
.venv/bin/ruff check .      # lint
```

`tests/tier1/` tests the pure parts (names, settings, rendering) against small invented templates;
`tests/tier2/` runs `new-lobster` end to end against stubs of `git`, `backlog`, `lobster-mail` and
Python placed on `PATH`, `local-history` against the stubs of `git` and `lobster-mail`, `conduct` against stubs of `lobster-mail` and `open`, `podium` against a stub of `conduct` (its request
handling as a plain function; three tests fetch the page from a real socket on `127.0.0.1`, which is this
machine and not the network), and `conform` against invented pairs, with no network. Coverage is 99%: the two uncovered lines handle a folder
that appears while `new-lobster` is running, a race the tests cannot stage.

Manual check of `local-history` against the real git (Tier 3): make a scratch folder with a file or two
and a small git repository inside it, run `./local-history --dry-run` on it and then without the flag, and
look: `git ls-files` lists the folder's own files and not the checkout's, `git status --short` and `git
remote` print nothing, and a file emptied on purpose comes back with `git checkout -- <file>`.

Manual check against the real programs (Tier 3): point `BERNSTEIN_CONF` at a settings file whose
`NON_CODE_DIR`, `CODE_DIR` and `MAIL_ROOT` are scratch folders, then run `./new-lobster --dry-run
<name>` and `./new-lobster <name>`, and look at what was made.
`./conduct status` and `./conduct status --json` read only, so they are run against the real mail root
and projects as they are. So is `./podium`: open its link, look at the page at full and at phone width,
in light and dark, press Refresh, then stop it with Ctrl-C and press Refresh again to see the page say so.
Its buttons are tried as far as Preview, which is `conduct`'s own dry run and sends nothing; Send is
tried only against a stand-in for `conduct`, never the real one, unless the message is really wanted.

## Known limitations and non-goals

- The GitHub owner in the printed commands is fixed (`douglassquirrel`); creating repositories is
  left to the user.
- One pair at a time; no bulk or scheduled use; macOS only.
- The template is not shipped with this repository.

## Notes for users

- 14 November 2026: a project's global files now give the ticket prefix its own Backlog uses
  (`task_prefix` in `backlog/config.yml`) where that differs from the first two letters of its name. A
  project set up before the template with a prefix of its own gets its shared rules corrected at its
  next `conduct start`; until then `conform` lists the file as behind.
- 14 November 2026: `conduct start` now refuses (exit 3) while a Start it sent to the same project less
  than ten minutes ago still waits unread, so pressing Start twice no longer sends two. To send another
  anyway, add `--again`.
- 13 November 2026: `new-lobster --public` (with or without `--claw`) now also starts a local history, with
  no remote, in the new tools project's outer folder. A private tools project is made as before.
- 13 November 2026: new command `local-history`: a git repository with no remote for the folder around a
  public checkout, where the rules, plan and diary live. It changes no file and never pushes.
- 18 October 2026: first versions of `new-lobster` and `conduct`.
- 18 October 2026: `conduct start` now refuses, sending and opening nothing, a project that lacks
  `START-HERE.txt`, a readable `lobster.conf`, a known KIND, MODEL or EFFORT, or (non-code) its
  sister tools project, instead of starting it or failing with a traceback.
- 18 October 2026: `conduct` also finds a project, and a non-code project's sister, one subfolder down
  (`~/projects/code/videos/video-tools`), so related projects can be kept together.
- 18 October 2026: `conduct` treats `lobster-mail`'s exit 7 (delivered, no sent copy) as sent, and never
  sends the message again.
- 18 October 2026: `new-lobster --render-into` renders the template for an existing pair into a new folder,
  for bringing it into line by hand.
- 18 October 2026: `conform <non-code> <tools>` lists what an existing pair lacks against the template.
- 1 November 2026: `conduct dormant` and `conduct wake`: a session sleeps without a handover (no mail
  checks, pace `relaxed`) and is woken by Squirrel speaking to it, or by `wake`.
- 1 November 2026: ganglia and claws. `lobster.conf` may name further claws (`CLAWS=a b`); a tools
  project with an empty `SISTER` is a lone claw. `new-lobster --claw <name>` makes one; `--render-into`
  takes `--claw` and `--claws`; `conduct start` connects every claw and its `<claw>-secrets` folder
  and finds a claw whose name does not end `-tools`; `conform <claw>` checks one alone, and a pair's
  check lists a claw that is missing.
- 1 November 2026: `conform` also lists a start hook without this mail root's `--root`, and an Inbox or
  Mail section whose wording is not the template's. A pair that was in line may now show new gaps.
- 8 November 2026: `conduct dream` asks a session to write proposals in its `dreams/` for a while, then go
  dormant (or hand over with `--then stop`). `conform` also checks the wording of the template's new
  "Dreams" section, and the template's Mail section now says a request from bernstein for a tool waits
  for Squirrel's OK, so a pair that was in line will show these as gaps.
- 8 November 2026: a dormant session, after `conduct dormant` or a dream, asks Squirrel nothing (no question,
  offer or reminder) until he next speaks to it.
- 10 November 2026: `conduct status [--json]` shows what every mailbox's session is doing. It reads only.
  The state `dormant` and the reported status need a `lobster-tools` that has `lobster-mail status`.
- 10 November 2026: `podium` shows the same on a page in your browser, served on this machine only while
  its command runs. A new setting, `PODIUM_PORT` (8417 unless set).
- 10 November 2026: `podium` has buttons for `conduct`'s verbs. Each shows a preview (the dry run) before
  anything is sent. Every run is added to a log, `~/.bernstein/podium.log` unless the new setting
  `PODIUM_LOG` says otherwise.
- 10 November 2026: podium's dialog shows what it is waiting for, and for how long, while `conduct` runs.
- 11 November 2026: `conduct status --json` gives each project a `session` link to its newest Claude Code
  session in the desktop app, and podium shows it as "Open". A new setting, `APP_SESSIONS`, says where the
  app keeps its sessions.
- 11 November 2026: podium names the session on duty "Claude Code" or "Claude Cowork", where it showed the
  mail names `mac` and `device`. `conduct status` still prints the mail names.
- 11 November 2026: the Stop message, and a dream that ends in a handover, now tell the session to archive
  itself as its last act, so finished sessions leave your list.
- 11 November 2026: the `session` link and podium's "Open" now cover a non-code project's Claude session
  too. `session` gains `app` (`code` or `cowork`), and there is a new setting, `APP_COWORK_SESSIONS`.
- 10 November 2026: podium's page is restyled (a cream page, white cards, an orange accent, a serif face) and
  made more compact: a line no longer says "nobody on duty", "pace normal", "0 new" or "0 open".
- 10 November 2026: the Dormant and Dream messages now tell a session to report `dormant` or `dreaming`
  with `lobster-mail status` and to clear it on waking; the Wake message tells it to clear it; the Start
  message tells a new session to clear a status an earlier one left. A session made dormant before this
  date shows as `quiet` once its duty is stale.
- 13 November 2026: `conduct start` names each session: the project and the day by default, or
  `--name TEXT`. The Start message now asks the session to title itself, and the first line you
  send begins with the name. podium's Start dialog has a "name" field.
- 13 November 2026: a template can name **global files** (`common/global-files`), which it owns in
  every project's folder. `conform` lists one that is missing or behind, and `conduct start` brings
  those that are behind up to date before it opens the session, keeping the old copies in the
  project's `_to_delete/`. A project without them all is not touched.
- 13 November 2026: **feelers**: `new-lobster --feeler <name>` makes a light project for one-off work
  (no tools project, Backlog or inbox; mail at the relaxed pace), `conduct` starts it like any
  project, and `conduct finish <feeler>` asks it to write up and hand over. A project's
  `lobster.conf` may now say `KIND=feeler`.
- 13 November 2026, later: the first line of a new session now begins "Session title: <name>.", and
  only a Claude Code session is asked to rename itself: a Claude Cowork session cannot (its first
  start under the new naming was titled "Literary agent folder setup" by the app).

## Contributing

Dev tooling (pytest, pytest-cov, ruff) goes in a `.venv` from `requirements-dev.txt`. Changes are
made test-first, on `main`.
