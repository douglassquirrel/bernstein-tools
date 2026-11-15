# bernstein

Tools that set up and run "lobster" projects: pairs of projects worked on with Claude, where a
non-code project does the work and asks a companion tools project, by mail, for every routine task
as a tested command. `new-lobster` makes such a pair in one step: both folders from a template,
git, a mailbox each, the first commits, and a Backlog issue tracker if you ask for one. `conduct` starts a project's
session and asks a running one to hand over, and `podium` shows every session on a page in your
browser, with buttons for what `conduct` does. `set-conf` changes one setting in a project's
`lobster.conf`, keeping the file as it was. `local-history` gives the private folder around a public
checkout a git history of its own, with no remote. They are for one person's Mac and their own
projects; the projects talk by `lobster-mail`, from the
[lobster-tools](https://github.com/douglassquirrel/lobster-tools) repository.

## Requirements

- macOS with `/usr/bin/python3` (3.9 or later) and `git`.
- Only for a project that keeps tickets (`--backlog`): Backlog, the `backlog.md` package (`backlog` on
  `PATH`; tested with 1.53.0).
- A checkout of `lobster-tools` for `lobster-mail`, and a mail root it can use.
- A lobster-project template: a folder with `common/`, `non-code/` and `code/`. It is not part of
  this repository; `new-lobster` reads it from the `TEMPLATE` setting. See "The template" below.

## Installation

```bash
git clone https://github.com/douglassquirrel/bernstein-tools.git
cd bernstein-tools
cp bernstein.conf.example ~/.bernstein.conf      # then edit what differs on your machine
./new-lobster --help
```

## Quick start

See what would be made, without making anything:

```
$ ./new-lobster --dry-run recipes
Make recipes: /Users/me/projects/non-code/recipes
Make recipes-tools: /Users/me/projects/code/recipes-tools
Then: git init -b main in each repository; lobster-mail init recipes and recipes-tools in /Users/me/projects/mail; a first commit in each; the tools' .venv.
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
new-lobster [--dry-run] [--public] [--backlog] [--template DIR] [--non-code-dir DIR] [--code-dir DIR]
            [--model MODEL] [--effort EFFORT] <name>
new-lobster --claw [--dry-run] [--public] [--backlog] <name>
new-lobster --feeler [--dry-run] [--claws "a b"] <name>
```

- `<name>`: the non-code project's name: lower-case letters, digits and single hyphens, starting
  with a letter, 2 to 40 characters, not ending in `-tools`. The tools project is `<name>-tools`.
- `--dry-run`: check everything and render every file, print what would be made, and stop.
  Nothing is written; the only program run is the read-only mailbox listing.
- `--backlog`: the project keeps tickets. Each half gets Backlog (`backlog init`, ids `RE-001` on for
  `recipes`), committed with its first commit, and its rules get the template's section on tickets.
  Without it, which is the default since 14 November 2026, `backlog` is never run and the rules say the
  project keeps no tickets. A project keeps tickets if and only if its folder has `backlog/config.yml`:
  a project that wants them later runs `backlog init` in its own folder, and one that never used them
  loses them with `drop-backlog` (below). Not with `--feeler`: a feeler keeps none.
- `--public`: the tools project is public. Its guidance files then stay in an outer folder,
  `<name>-tools-code/`, beside a checkout `<name>-tools/` that holds the code and an MIT licence. The outer folder also gets a git repository of its own, with no remote, started last of all with
  everything beside the checkout in it (what `local-history` does, below); a dry run says so in a line
  beginning "And:".
- `--template`, `--non-code-dir`, `--code-dir`, `--model`, `--effort`: override the settings below.

What it makes, for `recipes`: `<non-code dir>/recipes/` and `<code dir>/recipes-tools/`, each a git
repository on `main` with a first commit (and Backlog, with `--backlog`); the mailboxes `recipes` and
`recipes-tools`; and the tools project's `.venv` with its dev tooling. It never writes over
anything, never changes the template, never deletes, and never touches GitHub.

**Ganglia and claws.** A non-code project (a *ganglion*, where the work is done) has a *home claw*, the
tools project `new-lobster` makes with it, where its new tools are born; `lobster.conf` names it as
`SISTER`. It may also use further claws, other tools projects, named in a `CLAWS=word-tools
google-docs-tools` line. A claw that serves any project and has no non-code half of its own is a
*lone claw*: `KIND=code` and an empty `SISTER` in its `lobster.conf`.

**Making a lone claw.** `new-lobster --claw [--public] [--dry-run] <name>` makes one tools project
on its own: its folder (the public layout with `--public`), a git repository with a first commit,
one mailbox and the `.venv` (and Backlog, with `--backlog`), and prints the commands for its one GitHub repository. The
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
**Tickets.** In any template file `{{BACKLOG}}` is `yes` for a project that keeps tickets and `no` for one
that does not, so an include can choose between two sections, as in `{{> sections/backlog-{{BACKLOG}}.md}}`.
For a new project that is the `--backlog` flag; for an existing one, whether its folder has
`backlog/config.yml`. In a global file `{{BACKLOG_PREFIX}}` is the prefix the project's own tickets carry:
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

## A conductor and its claw

The project whose session runs these commands is a **conductor**. It is a fourth kind of project,
beside a non-code project, a tools project and a feeler, and it and the tools project that builds its
commands are a pair. The two say so in their `lobster.conf`:

```
# the conductor's, in <name>-code/ or <name>/ in the code folder
KIND=conductor
SELF=maestro
SISTER=maestro-tools
MODEL=fable
EFFORT=xhigh

# its claw's
KIND=code
SELF=maestro-tools
SISTER=maestro
```

A conductor is outside the template: its folder is the whole of it, with no checkout, and it needs no
`START-HERE.txt`, hook or `inbox/`. It has one claw, the one `SISTER` names; `CLAWS` or `FOLDERS` in its
`lobster.conf` are refused. What each command does with it:

- **`conduct start`, `finish`, `dormant`, `wake`, `dream`** refuse a conductor by name (exit 3, nothing
  sent, set or opened): it is the session that runs `conduct`, and you start and stop it yourself. With
  `--all`, `stop`, `dormant`, `wake` and `dream` pass over every conductor's mailbox, as they pass over
  the mailbox `bernstein`. `conduct reset` and `conduct stop <name>` work on a conductor as on any mailbox.
- **Its claw** is found, started, stopped and reset exactly as any tools project is. Its global files
  are rendered for a conductor: the template's `{{SERVED}}` is `conductor`, so a line `{{> sections/served-{{SERVED}}.md}}`
  takes `common/sections/served-conductor.md`, **which the template must have**, and the words that name
  the sister (`{{FOR_WHOM}}`, `{{REQUESTER}}`, `{{SERVING}}`, `{{TALKS_TO}}`, `{{ASKING}}`, `{{SEND_TO}}`,
  `{{OF_WHOM}}`, `{{NONCODE_PATH}}`) name the conductor and its folder. Without that section, `conduct
  start` and `conform` stop with exit 4, naming the file.
- **`conduct status`** gives a conductor the kind `conductor` and its claw in `claws`; the claw's row has
  the conductor in `serves`. **`podium`** shows the two as one card under "Conductor", the claw beneath
  the conductor; the conductor's line has no buttons, and the claw is not among the lone claws.
- **`conform <conductor> <claw>`** checks the claw as the tools half of the pair and, of the conductor,
  only what a conductor has: `lobster.conf` (`KIND=conductor`, `SELF`, `SISTER` naming the claw, `MODEL`,
  `EFFORT`, no `CLAWS` or `FOLDERS`), a CLAUDE.md, a git repository and a mailbox.
- **`set-conf` and `drop-backlog`** refuse a conductor (exit 3): its files are its own.

```
$ ./conduct status
maestro        running  conductor  on duty mac, last beat 2026-11-14T14:22:16Z (0 minutes ago)  new 0  open 0  pace normal
maestro-tools  off      code       nobody on duty  new 0  open 0  pace normal
$ ./conduct start maestro --dry-run
conduct: maestro is a conductor, the session that runs conduct: conduct start has nothing to do to it; Squirrel starts and stops it himself
$ ./conform maestro
conform: maestro is a conductor: give its claw too, as in conform maestro maestro-tools
```

## conduct: starting and stopping a project's session

```
conduct start   <project> [--brief FILE] [--pace eager|normal|relaxed] [--name TEXT] [--again] [--dry-run]
conduct stop    <project> | --all  [--wait SECONDS] [--dry-run]
conduct finish  <feeler>  [--dry-run]
conduct reset   <project> [--handover FILE] [--dry-run]
conduct dormant <project> | --all  [--dry-run]
conduct wake    <project> | --all  [--dry-run]
conduct dream   <project> | --all  [--minutes N] [--then dormant|stop] [--dry-run]
conduct status  [--json]
conduct waiting [--json]
```

`conduct` talks to a lobster project's session by mail, as `bernstein`; each project's guidance
says to act on bernstein's mail at once (since 8 November 2026, apart from a request for a tool,
which waits for Squirrel's OK). It reads who is on duty with `lobster-mail duty status
--all` and, at a start, the project's unread mail with `lobster-mail check`, and writes in a project's folder only to bring the template's global files up to date
at a start (below). Only `reset` acts in a project's mailbox as the project itself.

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
  **Further folders.** A non-code project or a feeler whose session needs a folder that is neither its
  own nor a claw's (a folder of downloaded models, say) names it in its `lobster.conf`:
  `FOLDERS=~/models/kokoro`, several separated by colons, each a full path or one starting `~/`. `start`
  connects them after the usual folders and says so ("Also connected, from FOLDERS in its lobster.conf:
  …"; a dry run: "Would also connect, …"). It refuses to start (exit 3, nothing sent or opened) if one is
  not a full path, is not a folder on this Mac, or has the same last name as another connected folder,
  since a session sees each as `~/mnt/<name>`; and for a tools project that names any, because a Claude
  Code session opens in one folder. `conduct status` then says the project cannot start, and why.
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
- **`reset`** is for a session that ended without handing over (the app lost it, the Mac slept, it was
  closed by mistake), so that the project's next session starts clean. It works in the project's mailbox,
  as the project, and does three things:
  1. closes every message `conduct` itself sent that session and that still waits, unread or claimed: the
     ones from `bernstein` whose subject begins `Start:`, `Stop:`, `Finish:`, `Dormant:`, `Wake:` or
     `Dream:`. A new session would otherwise act on a Stop meant for the one that is gone. Notices,
     requests, replies and the project's own handovers are left for the next session to read;
  2. gives up the lost session's duty, and with it the status that session reported;
  3. leaves a note in the mailbox as a handover, which the next session reads first: that bernstein reset
     the mailbox, which messages were closed, whose duty was given up, and then the lost session's own
     note if you have it (`--handover FILE`, passed on unchanged), or a line saying none was given.

  It refuses (exit 3) while a session is fresh on duty: stop that one with `stop`; if it has just died,
  run `reset` again once its duty has gone stale. A dormant session, and one at the relaxed pace, have a
  stale duty while they are still open in the app, so `reset` says so first and `--dry-run` shows
  everything it would do, the note included, and changes nothing: read it before the real run. With
  nobody on duty, nothing of `conduct`'s waiting and no note given, it does nothing and says so (exit 0).
  A `--handover` file that is missing, empty or not UTF-8 text is exit 2. Nothing is deleted: closed
  messages move to the mailbox's `done/`, and the duty's record to its `duty-log/`. If a step fails part
  way (exit 4), the message says what was closed and that the duty stands; run it again to finish.

  ```
  $ ./conduct reset recipes --handover ~/note-from-the-lost-session.md
  recipes: device is on duty but stale (last beat 2026-11-14T08:05:00Z).
  Closed in recipes's mailbox: 2026-11-14-0812-bernstein-stop-hand-over ("Stop: hand over")
  Left a note for recipes's next session, with the note from /Users/sq/note-from-the-lost-session.md, and gave up the duty of device (last beat 2026-11-14T08:05:00Z).
  recipes is reset: conduct start recipes will start it afresh.
  ```
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
- **`waiting`** shows what is waiting across every project: commits not pushed, files not committed, and
  bernstein's mail not dealt with. It reads only, so it has no `--dry-run`: it never fetches, pushes,
  claims or closes anything and writes no file.

  ```
  $ ./conduct waiting
  bernstein
    /Users/you/projects/code/bernstein-code: 1 file uncommitted

  recipes-tools
    /Users/you/projects/code/recipes-tools-code: no remote; 2 files uncommitted
    /Users/you/projects/code/recipes-tools-code/recipes-tools: 2 commits not pushed
    From bernstein, unread: "Notice: your rules changed" (sent 2026-10-18T08:00:00Z)
    From bernstein, claimed and not closed: "Stop: hand over" (sent 2026-10-17T16:00:00Z)
    To bernstein, unread: "Re: Request 3: built" (sent 2026-10-18T08:00:00Z)
    To bernstein, claimed and not closed: "Request 4: a flag" (sent 2026-10-18T08:00:00Z)

  salads (a mailbox with no project folder)
    From bernstein, unread: "Start: salads" (sent 2026-10-18T08:00:00Z)

  squirrel (no project folder and no mailbox)
    To bernstein, unread: "hello" (sent 2026-10-18T08:00:00Z)

  video-tools
    /Users/you/projects/code/video/video-tools: not a git repository

  Other repositories (not lobster projects):
    /Users/you/projects/code/video/halmos-code/halmos: 1 commit not pushed; 1 file uncommitted
    /Users/you/projects/non-code/writing/nötes: no upstream branch: never pushed

  Waiting: 3 commits not pushed, 4 files uncommitted, 3 messages from bernstein not dealt with, 3 messages to bernstein not closed, 1 repository never pushed, 1 folder not a git repository.
  Nothing waiting in 1 project and 2 other repositories.
  No remote and nothing uncommitted: 1 repository.
  ```

  - **What it looks at.** Every lobster project (a folder holding a `lobster.conf`, directly in
    `NON_CODE_DIR` or `CODE_DIR` or one folder down, as `conform --all` finds them); every mailbox under
    the mail root; and every other git repository directly in those two folders or one folder down that
    is not a lobster project and not inside one, with the `<x>/` inside a folder named `<x>-code/`.
    Those others are listed apart, git only.
  - **Git**, in a project's folder and, for a public tools project (`<name>-code/`), in the checkout
    `<name>/` inside it too. Commits not pushed are counted against the branch's upstream *as last
    fetched* (`git rev-list --count @{u}..HEAD`): nothing is fetched. A repository with a remote whose
    branch has no upstream is "never pushed". One with no remote has nothing to push and is listed only
    if something in it is uncommitted, as "no remote". Files uncommitted are the lines of `git
    --no-optional-locks status --porcelain`, untracked files included; with that flag git writes
    nothing, not even its index. A project's folder with no `.git` is "not a git repository".
  - **Mail.** For each mailbox but bernstein's own: the messages from `bernstein` in its `new/`
    ("unread") and `open/` ("claimed and not closed"), and the messages from it in bernstein's `new/`
    and `open/`, each with its subject (quoted as JSON quotes a string) and when it was sent. It asks
    `lobster-mail` only for the duty listing and for `list --new` and `list --open`.
  - **What is shown.** A block for each project with something waiting, by name; a mailbox with no
    project says "(a mailbox with no project folder)" and a project with no mailbox "(no mailbox)", but
    neither alone makes a block. Then the other repositories that wait, one line of totals, how many
    projects and other repositories have nothing waiting, and how many repositories have no remote and
    nothing uncommitted. In a block only the repositories with something to say are listed.
  - **`--json`** prints everything, the projects with nothing waiting too: `root`; `projects`, each with
    `name`, `folders`, `mailbox` (true or false), `repositories`, `from_bernstein`, `to_bernstein` and
    `waiting`; `other_repositories`; and `totals` (`projects`, `projects_waiting`, `other_repositories`,
    `other_repositories_waiting`, `commits_not_pushed`, `never_pushed`, `files_uncommitted`, `not_git`,
    `from_bernstein`, `to_bernstein`, `no_remote_nothing_uncommitted`). A repository is `folder`, `git`,
    `remote`, `upstream`, `unpushed`, `uncommitted` and `waiting`, with `null` where a thing does not
    apply (`unpushed` where there is no remote or no upstream). A message is `id`, `subject`, `sent` and
    `state` (`unread` or `claimed`).
  - **Exit codes.** 0 whenever the report is made, whatever is waiting: read `totals` in `--json` to
    know. 4 if `git` or `lobster-mail` cannot be run, fails, or prints what is not expected: the message
    names the repository or the mailbox, and nothing of the report is printed.

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
| 0 | Sent (and, with `--wait`, handed over); or, for `stop`, `dormant`, `wake` and `dream`, nobody on duty; or, for `status` and `waiting`, shown, whatever is waiting; or, for `reset`, reset or nothing to reset |
| 2 | Bad arguments or settings, or `--minutes` outside 5 to 240, or a brief or handover note that cannot be read |
| 3 | No such project or mailbox, or the project lacks a part `start` needs; or, for `start`, a session is already on duty, or a Start sent in the last ten minutes still waits unread; or, for `reset`, a session is fresh on duty |
| 4 | A program failed, or the duty listing or a list of the project's mail could not be read; for `waiting`, `git` failed in a repository too |
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
**Wake all** when any session but bernstein's or a conductor's is in that state; bernstein's own line
and a conductor's have no buttons.
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
conform <conductor> <its claw>
conform --all [--json]
```

`conform` reads an existing pair and lists, half by half, what it lacks against the template; it
changes nothing. With one name it checks a lone claw alone, as a code half with an empty SISTER,
and ends "The claw is in line." In a pair's check, a home claw whose `lobster.conf` has an empty
SISTER is a lone claw serving this project among others, and is checked as one. A conductor and its
claw are checked as "A conductor and its claw" above says; either of the two named alone is exit 2,
saying to name both. It finds each half
where `conduct` looks (one subfolder down included), then checks: `lobster.conf` (readable, with the right KIND, SELF and SISTER and a MODEL
and EFFORT), for a non-code project every claw in CLAWS present in the code folder, `START-HERE.txt`,
`.claude/settings.json` with the `lobster-mail start` hook passing this mail root to `--root`,
`inbox/README.md`, CLAUDE.md having each section the template's CLAUDE.md for that half takes from
`common/sections/` and each heading naming the pair, the Inbox and Mail sections in the template's
exact wording (blank lines aside), every folder named in FOLDERS present (and none named by a tools
project), a git repository, the mailbox, and, for a public tools
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

### conform --all: every project in one run

`conform --all` finds every lobster project the settings can find and checks each once, in the form
that fits it. A project is a folder holding a `lobster.conf`, directly in the non-code or the code folder
or one folder down; hidden folders are left out, and a folder that is a project is not searched for
more. The blocks come in this order: each non-code project with the home claw its `SISTER` names; each
conductor with its claw; each feeler; then every tools project not yet checked, alone if its `SISTER` is
empty, otherwise as the tools half of the pair its `SISTER` names. A half checked in an earlier block
(a lone claw that is home to two projects) says "see above" the second time.

Each gap is one of two kinds, and the last line counts them apart:

- **`a start mends:`** a global file that is behind the template, in a project that keeps every global
  file: the project's next `conduct start` replaces it, so nobody need act.
- **`missing:`** everything else, which nothing mends by itself. That includes a global file that is
  behind in a project that lacks another global file, since `conduct start` leaves such a project's
  files as they are.

```
$ ./conform --all
menus (non-code): /Users/me/projects/non-code/menus
  in line
menus-tools (code): /Users/me/projects/code/menus-tools
  in line

recipes (non-code): /Users/me/projects/non-code/eat/recipes
  a start mends: the template's current RULES.md (a global file: conduct start brings it up to date)
recipes-tools (code): /Users/me/projects/code/eat/recipes-tools-code
  a start mends: the template's current RULES.md (a global file: conduct start brings it up to date)

word-tools (code): /Users/me/projects/code/word-tools
  missing: START-HERE.txt
  missing: the mailbox word-tools in /Users/me/projects/mail

odd: cannot be checked
  /Users/me/projects/non-code/odd/lobster.conf is not plain UTF-8 text: save it again as UTF-8

bernstein: a mailbox in /Users/me/projects/mail with no lobster project
6 projects: 2 things to bring into line, 2 more that a conduct start mends, 1 project that could not be checked.
```

A project that cannot be checked is listed with the reason and the run goes on: a name in two places,
a `lobster.conf` that cannot be read or is not UTF-8, an unknown `KIND`, a non-code project or conductor
that names no `SISTER`, a tools project that names a feeler as its sister, a project whose own Backlog
settings cannot be read. A half listed that way further down says "see below" where a pair names it. A
template that cannot be used still stops the run (exit 4). A folder in the mail root that is no found
project's mailbox is said in a line and counted nowhere.

`--json` prints the same as data: `blocks`, each a list of halves (`name`, `kind`, `folder`, `state`:
`checked`, `not found`, `cannot be checked`, `see above` or `see below`; `why`; `gaps`, each with
`missing` and `start_mends`), `mailboxes_without_a_project`, and `totals` (`projects`,
`nothing_mends`, `a_start_mends`, `cannot_be_checked`).

Exit codes with `--all`: 0 when nothing is of the second kind and everything could be checked (gaps a
start mends do not count); 1 otherwise; 2 `--all` with a project named, or `--json` without `--all`; 4
the template cannot be used. It reads only, and runs no other program.

## drop-backlog: take Backlog out of a project that never used it

```
drop-backlog [--dry-run] PROJECT [PROJECT ...]
```

Backlog used to be set up in every project. For one that has never held a ticket, `drop-backlog` moves
the whole `backlog/` folder into that project's `_to_delete/backlog-removed-<date>-<time>/`, so nothing
is lost and it can be put back by moving it back. It changes nothing else in the project and commits
nothing: the project's next session commits the removal, and its shared rules say "no tickets" from its
next `conduct start`. Run it with `--dry-run` first.

Everything is checked before anything moves, and one refusal stops the whole run (exit 3):

- a Backlog that holds any file besides its `config.yml` (a ticket, a draft, a decision, a document) is
  in use and is left alone; the message counts the files and names the first three;
- a project with anyone on duty, fresh or stale, is not changed under its session: stop it with
  `conduct stop`, or `conduct reset` if it is gone;
- a project that cannot be found, or is in two places, or whose `backlog` is a link.

A project with no `backlog/` already is passed over with a line. A project with no mailbox has nobody
on duty and is done like any other.

```
$ ./drop-backlog --dry-run recipes recipes-tools
recipes: would move /Users/me/projects/non-code/recipes/backlog to /Users/me/projects/non-code/recipes/_to_delete/backlog-removed-2026-11-14-1210/backlog
recipes-tools: would move /Users/me/projects/code/recipes-tools/backlog to /Users/me/projects/code/recipes-tools/_to_delete/backlog-removed-2026-11-14-1210/backlog
Dry run: nothing was moved.
```

Exit codes: 0 moved, would move, or nothing to remove; 2 bad arguments or settings; 3 refused, nothing
moved; 4 the duty listing could not be had, or a move failed (the message says which were moved).

## set-conf: set one line in a project's lobster.conf

```
set-conf [--dry-run] PROJECT KEY=VALUE
```

A project's `lobster.conf` says which tools projects and further folders its session is connected to
and which model and effort it must run on. `set-conf` changes one of those settings in one project:
`SISTER`, `CLAWS`, `FOLDERS`, `MODEL` or `EFFORT`. It never changes `KIND` or `SELF`, which say what the
project is, and it knows no other key. Run it with `--dry-run` first.

```
$ ./set-conf --dry-run demo FOLDERS=/Users/me/models/voices
demo: /Users/me/projects/non-code/demo/lobster.conf
  is:       (no FOLDERS line)
  would be: FOLDERS=/Users/me/models/voices (added as the last line)
  the file as it is would be kept in /Users/me/projects/non-code/demo/_to_delete/before-conf-change-2026-11-14-1354/lobster.conf
Dry run: nothing was changed. After the real run demo is owed a notice by mail of the change.
$ ./set-conf demo FOLDERS=/Users/me/models/voices
demo: /Users/me/projects/non-code/demo/lobster.conf
  was: (no FOLDERS line)
  now: FOLDERS=/Users/me/models/voices (added as the last line)
  the file as it was is kept in /Users/me/projects/non-code/demo/_to_delete/before-conf-change-2026-11-14-1354/lobster.conf
Nothing was committed and nothing was sent: demo is owed a notice by mail of this change.
$ ./set-conf demo MODEL=fable
demo: /Users/me/projects/non-code/demo/lobster.conf
  was: MODEL=opus
  now: MODEL=fable
  the file as it was is kept in /Users/me/projects/non-code/demo/_to_delete/before-conf-change-2026-11-14-1354-2/lobster.conf
Nothing was committed and nothing was sent: demo is owed a notice by mail of this change.
```

What it changes, and what it leaves:

- **One line.** If the file has a line for the setting, the value on that line is replaced: everything
  up to and including the `=` stays, and so does the line's ending. If the setting is written on several
  lines, the last is changed, since that is the one `conduct` reads, and the output says so. If the file
  has no such line, `KEY=VALUE` is added as its last line. Every other byte stays as it was: comments, the
  order, CRLF line endings. (When a line is added to a file whose last line has no ending, that line
  gains one.)
- **The whole rest of the line is the value**, as `conduct` reads it: there are no comments after a
  value. Spaces at either end of VALUE are dropped. An empty value is allowed (`CLAWS=`).
- **Nothing to change** is said in a line, with exit 0, when the setting already reads as that value.
- **The file as it was** is copied first to `_to_delete/before-conf-change-<date>-<time>/lobster.conf` in
  the project's own folder (`-2`, `-3` for more in the same minute; never over an earlier copy). The new
  file is written beside the old one as `lobster.conf.set-conf-new` and renamed into place, so
  `lobster.conf` is never half-written. To undo a change, copy the kept file back.
- **Nothing else.** It commits nothing, sends no mail and writes nowhere else. Its last line reminds you
  that the project should be told by mail.

It refuses, changing nothing and leaving nothing behind (exit 3), each in a line of its own words:

- `KIND` or `SELF`, a setting it does not know, or a value with a line break in it;
- a project that cannot be found or is in two places; a folder with no `lobster.conf`; a `lobster.conf`
  that is a link, cannot be read or is not UTF-8;
- a value that would stop the project from starting: the file as it would be must pass everything
  `conduct start` checks (a `FOLDERS` entry that is not a folder or not a full path, `FOLDERS` for a
  tools project, a claw or sister that cannot be found, an empty `MODEL` or `EFFORT`), and `MODEL` must be
  one word and `EFFORT` one of `low`, `medium`, `high`, `xhigh`, `max`. Only the file as it would be is
  judged, so a setting that is wrong now can be put right;
- a project with anyone on duty, fresh or stale: stop it with `conduct stop`, or `conduct reset` if it
  is gone;
- a file already at `lobster.conf.set-conf-new`: look at it and move it away.

Exit codes: 0 changed, would change, or nothing to change; 2 bad arguments or settings; 3 refused,
nothing changed; 4 the duty listing could not be had, or the write failed (`lobster.conf` is as it was,
and what the run had made is taken away again, or named if it could not be).

## notice: one notice to several projects, each with its own facts

```
notice [--dry-run] --subject TEXT --body FILE [--facts FILE] [--keep DIR] PROJECT [PROJECT ...]
```

When something is changed in several projects, each is told by mail what was changed, when, and where
the old copy is. `notice` sends that message to each project named, as `bernstein` (the mailbox
`conduct` sends from), with each project's own facts filled into the same body. Run it with `--dry-run`
first: it prints every notice whole, exactly as it would be sent, and sends nothing.

**The body** is a text file. A place to fill is written `{{NAME}}`, in capitals and underscores;
anything else in double braces is left as written. `{{PROJECT}}` is the project's name and `{{FOLDER}}`
its folder; every other name comes from the facts file. A value is put in once and is never itself
filled. The subject is sent as given.

**The facts file** (`--facts`) is JSON, one block a project, a name in capitals for each fact, each
value text:

```
{
 "demo": {
  "KEPT": "/Users/me/projects/non-code/demo/_to_delete/before-conf-change-2026-11-14-1555/lobster.conf",
  "KEY": "EFFORT",
  "WAS": "EFFORT=high",
  "NOW": "EFFORT=max",
  "WHEN": "14 November 2026, 15:55Z"
 }
}
```

Nobody need type one: `drop-backlog`, `set-conf` and `conduct start` each take **`--facts-to FILE`** and
write there what they did, so that what the notice says is what the command did. The file is made if
it is not there; otherwise the project's block is added or replaced and the others are kept. A dry run
writes nothing there. `drop-backlog` gives `KEPT` and `WHEN` for each project it moved; `set-conf` gives
`KEPT`, `KEY`, `WAS`, `NOW` and `WHEN` when it changed the file; `conduct start` gives `KEPT`, `FILES` and
`WHEN` when it replaced global files. A file there that is not a facts file, or a folder that is not
there, is exit 2 before the command does anything.

```
$ ./set-conf --facts-to facts.json demo EFFORT=max
$ ./notice --dry-run --subject "Notice: a trial of notice" --body body.md --facts facts.json demo
Would send to demo, as bernstein, subject "Notice: a trial of notice":

To demo, a trial.

In /Users/me/projects/non-code/demo the line EFFORT=high became EFFORT=max on 14 November 2026, 15:55Z.
The file as it was: /Users/me/projects/non-code/demo/_to_delete/before-conf-change-2026-11-14-1555/lobster.conf

Dry run: nothing was sent.
$ ./notice --subject "Notice: a trial of notice" --body body.md --facts facts.json --keep kept demo
Sent to demo: 2026-11-14-1555-bernstein-notice-a-trial-of-notice (kept as kept/2026-11-14-1555-bernstein-notice-a-trial-of-notice.md)
Sent 1 notice as bernstein, subject "Notice: a trial of notice".
$ ./notice --subject "Notice: a trial of notice" --body body.md --facts facts.json demo
demo already has this notice unread (2026-11-14-1555-bernstein-notice-a-trial-of-notice): it is passed over.
Nothing was sent: every project named already has this notice unread.
```

Everything is checked before anything is sent, and one fault means nothing is sent to anyone:

- exit 2: a subject of more than one line; a body or facts file that cannot be read or is not what it
  should be; `--keep` naming something that is not a folder; a project named twice;
- exit 3: an empty subject or body; a facts block for a project that is not named; a project with no
  mailbox; a place in the body with no fact for some project (the message names the place and the
  project; `{{FOLDER}}` for a project with no folder is one).

**Never twice.** A project that already has this very notice unread (a message from `bernstein` in its
`new/` with the same subject and the same body, by its `Body-SHA-256`) is passed over with a line, in a
dry run too. One it has already claimed or closed does not count.

**`--keep DIR`** writes each notice as it was sent to `DIR/<id>.md` (`From`, `To`, `Subject` and `Id`
lines, a blank line, the body), never over a file.

If a send fails, the run stops there with exit 4, naming those already sent, with their ids, and those
not attempted; nothing is retried. Run it again naming only those that did not get it. A message that
`lobster-mail` delivered without keeping bernstein's own copy (its exit 7) counts as sent and is said on
standard error. Exit codes: 0 sent, would send, or everyone already had it; 2 bad arguments or
settings; 3 refused, nothing sent; 4 a listing could not be had, or a send or a kept copy failed.

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
`conform`, `drop-backlog`, `set-conf`, `notice` and `local-history` give their own codes in their sections above.)

| Code | Meaning | What to do |
|---|---|---|
| 0 | Done, or a dry run | |
| 2 | A bad name, flag or settings line | The message names the rule or the line; `--help` shows the form |
| 3 | A folder or a mailbox it would make already exists | Choose another name, or move the existing one yourself |
| 4 | The template cannot be used (missing, a missing include, an unknown placeholder) | Fix the template; nothing was written |
| 5 | A program it runs failed (`git`, `lobster-mail`, Python, or `backlog` with `--backlog`) | The message says what failed and lists what was already made, which is left as it is |

## Testing

```bash
/usr/bin/python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest            # all tests, with coverage
.venv/bin/ruff check .      # lint
```

`tests/tier1/` tests the pure parts (names, settings, rendering) against small invented templates;
`tests/tier2/` runs `new-lobster` end to end against stubs of `git`, `backlog`, `lobster-mail` and
Python placed on `PATH`, `local-history` against the stubs of `git` and `lobster-mail`, `drop-backlog`, `set-conf` and `notice` against invented projects and the stub of `lobster-mail`, `conduct` against stubs of `lobster-mail` and `open` (and, for `conduct waiting`, of `git`, which prints what each invented repository is given to say), `podium` against a stub of `conduct` (its request
handling as a plain function; three tests fetch the page from a real socket on `127.0.0.1`, which is this
machine and not the network), and `conform` against invented pairs, with no network. Coverage is 99%: the two uncovered lines handle a folder
that appears while `new-lobster` is running, a race the tests cannot stage.

The stubs are one shell script, `tests/tier2/stub.sh`, which acts by the name it is called as; each test
links to it under each program's name in a folder of its own and never writes to it (a test that needs a
different stub removes its link and writes its own file). It is one shared file because macOS takes about
a sixth of a second over the first run of a script it has not seen: with a new script for every test the
suite took 72 seconds, with links to one it takes about 25.

Manual check of `local-history` against the real git (Tier 3): make a scratch folder with a file or two
and a small git repository inside it, run `./local-history --dry-run` on it and then without the flag, and
look: `git ls-files` lists the folder's own files and not the checkout's, `git status --short` and `git
remote` print nothing, and a file emptied on purpose comes back with `git checkout -- <file>`.

Manual check of `set-conf` against the real `lobster-mail` (Tier 3), only ever on scratch folders: with
`BERNSTEIN_CONF` naming a settings file whose `NON_CODE_DIR`, `CODE_DIR` and `MAIL_ROOT` are scratch
folders, make a project there by hand (a `lobster.conf` and a `START-HERE.txt`) and its mailbox with
`lobster-mail init`; run `./set-conf --dry-run <name> FOLDERS=<a real folder>` and compare the file
with a copy (`cmp`); run it for real and compare the kept copy with that same copy; run it again to see
"nothing to change"; take the duty with `lobster-mail duty take` and see the refusal; then `./conduct
start --dry-run <name>` names the folder under "Would also connect".

Manual check of `notice` against the real `lobster-mail` (Tier 3), only ever on a scratch mail root: with
`MAIL_ROOT` a scratch folder, make there the mailboxes of two scratch projects and one named `bernstein`
(`lobster-mail init`); write facts with `./set-conf --facts-to`; run `./notice --dry-run`, then for real
with `--keep`, and read the mailboxes with `lobster-mail list`; run it again to see both passed over.

Manual check against the real programs (Tier 3): point `BERNSTEIN_CONF` at a settings file whose
`NON_CODE_DIR`, `CODE_DIR` and `MAIL_ROOT` are scratch folders, then run `./new-lobster --dry-run
<name>` and `./new-lobster <name>`, and look at what was made.
`./conduct status` and `./conduct status --json` read only, so they are run against the real mail root
and projects as they are. So is `./podium`: open its link, look at the page at full and at phone width,
in light and dark, press Refresh, then stop it with Ctrl-C and press Refresh again to see the page say so.
`./conduct waiting` reads only too, but whoever builds it tries it only on scratch folders: make a few
small repositories there with the real git (level with a bare origin, ahead of it with a file changed and
one untracked, with no remote, with a remote and no upstream, and a `<x>-code/<x>`), run `./conduct waiting`
and `./conduct waiting --json`, and check that no file under the scratch folders is newer than the run and
that every `.git/index` is byte for byte as it was.
`conduct reset` is tried only on a scratch mail root (`MAIL_ROOT` in a scratch settings file): make a
mailbox there with the real `lobster-mail`, send it a Stop as `bernstein`, take its duty, give the duty's
`heartbeat` file an old time, then run `./conduct reset <name> --dry-run` and the real run, and read the
mailbox with `lobster-mail start`.
Its buttons are tried as far as Preview, which is `conduct`'s own dry run and sends nothing; Send is
tried only against a stand-in for `conduct`, never the real one, unless the message is really wanted.

## Known limitations and non-goals

- The GitHub owner in the printed commands is fixed (`douglassquirrel`); creating repositories is
  left to the user.
- One pair at a time; no bulk or scheduled use; macOS only.
- The template is not shipped with this repository.

## Notes for users

- 15 November 2026: new verb `conduct waiting [--json]` shows what is waiting across every project:
  commits not pushed, files not committed (in a public tools project, in the checkout and in the folder
  around it), bernstein's messages to each project not yet dealt with, and each project's messages to
  bernstein not yet closed; then the other git repositories in the project folders, a line of totals,
  and how many have nothing waiting. It reads only: it never fetches, so "not pushed" is as last
  fetched. It exits 0 whenever it could make its report, whatever is waiting, and 4 if `git` or
  `lobster-mail` failed. Nothing else changes: `conduct status` is as it was.
- 14 November 2026: new command `notice [--dry-run] --subject TEXT --body FILE [--facts FILE] [--keep DIR]
  PROJECT ...` sends one notice to several projects as `bernstein`, each with its own facts filled in,
  checks everything before sending anything, and passes over a project that already has the notice
  unread. And `drop-backlog`, `set-conf` and `conduct start` take a new flag, `--facts-to FILE`, which
  writes what they did as the facts file `notice --facts` reads. Without the flag they behave as before.
- 14 November 2026: new form `conform --all [--json]` checks every lobster project the settings can
  find in one run, each once, and counts apart the gaps a `conduct start` mends by itself ("a start
  mends:") from those nothing mends ("missing:"). Its exit code is 0 unless something is of the second
  kind or a project could not be checked. `conform` with a project named prints and exits as before.
- 14 November 2026: **a conductor is a kind of project.** The project whose session runs these commands
  can say `KIND=conductor` and `SISTER=<its claw>` in a `lobster.conf` of its own, and its claw
  `SISTER=<the conductor>`: `conduct status` and `podium` then show the two as a pair, `conform <conductor>
  <claw>` checks both, and the claw's global files are rendered for a conductor, which needs a new
  section in the template, `common/sections/served-conductor.md`. `conduct start`, `finish`, `dormant`,
  `wake` and `dream` refuse a conductor, `--all` passes it over, and `set-conf` and `drop-backlog` refuse
  it. `conduct status --json`: a row's `kind` may now be `conductor`. An unknown `KIND` is now refused
  with "it must be code, non-code, feeler or conductor". Nothing changes for other projects.
- 14 November 2026: new command `set-conf [--dry-run] PROJECT KEY=VALUE` sets one of `SISTER`, `CLAWS`,
  `FOLDERS`, `MODEL` or `EFFORT` in a project's `lobster.conf`, keeping the file as it was in the
  project's `_to_delete/`. It refuses while anyone is on duty for the project, and any value with which
  `conduct start` would refuse the project. Run it with `--dry-run` first. Exit codes 0, 2, 3, 4 as
  `drop-backlog`'s.
- 14 November 2026: this repository is now named `bernstein-tools` (it was `bernstein`). An existing
  clone needs its address changed once: `git remote set-url origin
  https://github.com/douglassquirrel/bernstein-tools.git`.
- 14 November 2026: a non-code project or a feeler can name further folders for its session in its
  `lobster.conf`, `FOLDERS=~/models/kokoro` (colons between several); `conduct start` connects them and
  `conform` checks they are there.
- 14 November 2026: **Backlog is optional.** `new-lobster` no longer sets it up unless you add
  `--backlog`; `conform` no longer asks for a `backlog/` folder; a template can choose a section by
  `{{BACKLOG}}` (`yes` or `no`); and the new command `drop-backlog` moves an unused `backlog/` out of an
  existing project into its `_to_delete/`. A project that holds tickets is never touched.
- 14 November 2026: new verb `conduct reset <project> [--handover FILE] [--dry-run]`, for a session that
  ended without handing over: it closes the messages `conduct` had sent it, gives up its duty and leaves a
  note for the next session. Run it with `--dry-run` first.
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
