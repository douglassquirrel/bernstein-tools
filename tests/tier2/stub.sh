#!/bin/sh
# The stand-in for every external program the Tier 2 tests need (git, backlog, lobster-mail, python3, open,
# conduct, pip, claude). One file for them all: each test's World links to it by each program's name, and it acts by
# the name it was called as. It is a file of its own, never written by a test, because macOS takes about a
# sixth of a second over the first run of a script it has not seen, and a few thousandths over a link to one
# it has. Its folder of canned answers and its log are the first folder of PATH, which is the World's bin.
# tests/tier2/conftest.py says what each name prints and how a test makes one fail.
set -f
here=${PATH%%:*}
name=${0##*/}
last=; prev=; brief=; as=; to=; json=
for a in "$@"; do
    [ "$prev" = --brief ] && brief=$a
    [ "$prev" = --as ] && as=$a
    [ "$prev" = --to ] && to=$a
    [ "$a" = --json ] && json=1
    last=$a; prev=$a
done
{
    printf 'prog\0%s\0cwd\0%s\0' "$name" "$(pwd -P)"
    for a in "$@"; do printf 'arg\0%s\0' "$a"; done
    if [ "$last" = - ]; then printf 'stdin\0'; /bin/cat; printf '\0'; fi
    if [ "$name" = conduct ] && [ -n "$brief" ] && [ "$last" != --brief ]; then
        printf 'brief\0'; /bin/cat "$brief"; printf '\0'
    fi
    printf 'end\0.\0'
} >> "$here/calls.log"
if [ -f "$here/fail" ]; then
    for rule in $(/bin/cat "$here/fail"); do
        prog=${rule%%:*}; rest=${rule#"$prog"}; rest=${rest#:}
        verb=${rest%%:*}; code=${rest#"$verb"}; code=${code#:}
        if [ "$prog" = "$name" ] && { [ -z "$verb" ] || [ "$verb" = "${1-}" ]; }; then
            echo "$name: stub failure" >&2
            exit "${code:-1}"
        fi
    done
fi
none='{"root": "", "mailboxes": [], "skipped": []}'
show() { if [ -f "$here/$1" ]; then /bin/cat "$here/$1"; echo; else echo "$2"; fi; }
case "$name" in
lobster-mail)
    if [ "${1-}" = duty ] && [ "${2-}" = status ] && [ "${3-}" = --all ]; then show duty.json "$none"; fi
    if [ "${1-}" = check ]; then show check.json "[]"; fi
    if [ "${1-}" = list ]; then
        box=new
        for a in "$@"; do [ "$a" = --open ] && box=open; done
        if [ -f "$here/list-$box-$as.json" ]; then /bin/cat "$here/list-$box-$as.json"; echo
        else show "list-$box.json" "[]"
        fi
    fi
    if [ "${1-}" = send ] && [ -n "$json" ]; then
        printf '{"id": "2026-10-18-0940-bernstein-to-%s", "to": "%s"}\n' "$to" "$to"
    fi
    if [ "${1-}" = read ] && [ -f "$here/read-$last.txt" ]; then /bin/cat "$here/read-$last.txt"; fi ;;
conduct)
    if [ "${1-}" = status ]; then
        if [ -f "$here/status.json" ]; then /bin/cat "$here/status.json"; else printf '%s' "$none"; fi
    elif [ $# -ge 2 ]; then echo "conduct stub: $1 $2"
    else echo "conduct stub: ${1-}"
    fi ;;
git)
    verb=
    for a in "$@"; do case "$a" in -*) ;; *) verb=$a; break ;; esac; done
    if [ -n "$verb" ] && [ -f ".git/stub-$verb" ]; then /bin/cat ".git/stub-$verb"; fi
    if [ -n "$verb" ] && [ -f ".git/stub-$verb-exit" ]; then exit "$(/bin/cat ".git/stub-$verb-exit")"; fi ;;
claude)
    if [ "${1-}" = agents ] && [ "${2-}" = --json ]; then show live.json "[]"; fi ;;
python3)
    if [ "${1-}" = -m ] && [ "${2-}" = venv ]; then
        /bin/mkdir -p "$3/bin" && /bin/ln -s "$0" "$3/bin/pip"
    fi ;;
esac
exit 0
