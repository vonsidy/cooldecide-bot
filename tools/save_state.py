"""Commit the bot's state files back to the repo without losing a concurrent run's work.

Replaces the inline `git add / commit / pull --rebase || true / push || echo` the
workflow used to run. That version failed SILENTLY and lost data: when the rebase
hit a conflict it stopped on a detached HEAD, `git push` then failed with "you are
not currently on a branch", and the `|| echo "nothing to push"` fallback made the
step exit 0 anyway. A green check meant "pushed" and "threw your state away"
equally. On 2026-07-19 that dropped a posted video (JUFdeYK8DJ4) out of the
dashboard AND out of the no-repeat bank — it was live on the channel with nothing
in the repo knowing it existed.

The strategy here never rebases, so there is nothing to conflict:

  1. snapshot our state files in memory
  2. hard-reset the checkout onto the freshly-fetched remote branch
  3. merge our snapshot INTO that fresh base — a UNION, not an overwrite: a sibling
     run's video has to survive our write, and ours has to survive theirs
  4. commit and push; if someone pushed in between, the push is rejected, so loop
     and redo from (2) against the newer base

If it still can't push after ATTEMPTS tries it exits NON-ZERO. A state save that
didn't happen must fail the job — that's the whole point of this rewrite.

Only the append-mostly JSON is merged (dashboard/kids.json, the output/used_*.json
no-repeat banks, assets/art/prompts.json). Generated art is binary and purely
additive: `git reset --hard` leaves untracked files alone, so new .jpg files simply
survive each pass and get re-added.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Paths committed back. Globs are resolved fresh each attempt, since a reset can
# change which used_*.json files exist.
STATE_GLOBS = [
    "dashboard/kids.json",
    "output/used_*.json",
    "assets/art/prompts.json",
]
# Added wholesale (binary art). Not merged — additive by nature.
ADD_PATHS = ["assets/art"]

ATTEMPTS = 5


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=_HERE, check=check,
        capture_output=True, text=True,
    )


def branch() -> str:
    """The branch to push to.

    GITHUB_REF_NAME first: if the checkout ever lands detached again, rev-parse
    would report "HEAD" and we'd push nowhere useful.
    """
    env = os.environ.get("GITHUB_REF_NAME")
    if env:
        return env
    name = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    return name if name and name != "HEAD" else "main"


def state_files() -> list[str]:
    out: list[str] = []
    for pattern in STATE_GLOBS:
        out += sorted(glob.glob(os.path.join(_HERE, pattern)))
    return out


def read_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # kids.json is committed indent=2 by dashboard._save; the used_* banks are
        # written compact by content._save_used. Matching each keeps the diffs
        # readable instead of rewriting the whole file every run.
        if isinstance(data, dict):
            json.dump(data, f, indent=2)
        else:
            json.dump(data, f)


def merge_videos(theirs: list, ours: list) -> list:
    """Union by video id. Stats take the HIGHER of the two — either side may hold a
    fresher refresh_stats — and everything else prefers ours."""
    by_id: dict[str, dict] = {}
    for v in list(theirs) + list(ours):
        vid = v.get("id")
        if not vid:
            continue
        if vid in by_id:
            prev = by_id[vid]
            merged = {**prev, **v}
            for stat in ("views", "likes", "comments"):
                merged[stat] = max(int(prev.get(stat) or 0), int(v.get(stat) or 0))
            by_id[vid] = merged
        else:
            by_id[vid] = dict(v)
    return sorted(by_id.values(), key=lambda v: str(v.get("date") or ""), reverse=True)


def merge_by_key(theirs: list, ours: list, key) -> list:
    """Union of two lists, first occurrence wins, order preserved."""
    seen, out = set(), []
    for item in list(theirs) + list(ours):
        k = key(item)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


def merge_kids(theirs: dict, ours: dict) -> dict:
    merged = {**theirs, **ours}
    merged["videos"] = merge_videos(theirs.get("videos") or [], ours.get("videos") or [])
    merged["runs"] = sorted(
        merge_by_key(theirs.get("runs") or [], ours.get("runs") or [],
                     lambda r: (r.get("time"), r.get("title"))),
        key=lambda r: str(r.get("time") or ""), reverse=True,
    )[:200]
    merged["pending_comments"] = merge_by_key(
        theirs.get("pending_comments") or [], ours.get("pending_comments") or [],
        lambda q: (q.get("video_id"), q.get("due")),
    )

    # ClipCheck reports have no stable id, so dedupe on content.
    t_cc, o_cc = theirs.get("clipcheck") or {}, ours.get("clipcheck") or {}
    if t_cc or o_cc:
        reports = merge_by_key(t_cc.get("reports") or [], o_cc.get("reports") or [],
                               lambda r: json.dumps(r, sort_keys=True))
        cc = {**t_cc, **o_cc, "reports": reports[:25]}
        cc["latest"] = o_cc.get("latest") or t_cc.get("latest")
        merged["clipcheck"] = cc

    # `updated` must never go backwards; `started` is the earliest we ever saw.
    merged["updated"] = max(str(theirs.get("updated") or ""), str(ours.get("updated") or ""))
    started = [s for s in (theirs.get("started"), ours.get("started")) if s]
    if started:
        merged["started"] = min(started)
    return merged


def merge(path: str, theirs, ours):
    """Merge our snapshot into the freshly-fetched version of one state file."""
    if theirs is None:
        return ours
    if ours is None:
        return theirs
    name = os.path.basename(path)
    if name == "kids.json" and isinstance(ours, dict) and isinstance(theirs, dict):
        return merge_kids(theirs, ours)
    if isinstance(ours, list) and isinstance(theirs, list):
        # used_*.json: sets of "a|b" keys, stored sorted (content._save_used).
        return sorted(set(theirs) | set(ours))
    if isinstance(ours, dict) and isinstance(theirs, dict):
        return {**theirs, **ours}          # prompts.json: key -> prompt
    return ours


def attempt(snapshot: dict, br: str) -> bool:
    """One fetch -> reset -> merge -> commit -> push cycle. True if pushed (or if
    there was genuinely nothing to save).

    Any git failure here — a flaky fetch as much as a lost push race — just ends
    this attempt so the caller can retry from a clean fetch. The snapshot lives in
    memory, so redoing the cycle is always safe.
    """
    try:
        git("fetch", "-q", "origin", br)
        git("reset", "-q", "--hard", f"origin/{br}")

        for path, ours in snapshot.items():
            write_json(path, merge(path, read_json(path), ours))

        for pattern in STATE_GLOBS + ADD_PATHS:
            git("add", "--", *glob.glob(os.path.join(_HERE, pattern)) or [pattern],
                check=False)

        if git("diff", "--cached", "--quiet", check=False).returncode == 0:
            print("state save: nothing changed")
            return True

        git("commit", "-q", "-m", "Update CoolDecide data [skip ci]")
        push = git("push", "-q", "origin", f"HEAD:{br}", check=False)
        if push.returncode == 0:
            print(f"state save: pushed to {br}")
            return True
        print(f"state save: push rejected ({push.stderr.strip()[:200]}) "
              f"— retrying on newer base")
    except subprocess.CalledProcessError as e:
        print(f"state save: {' '.join(e.cmd)} failed "
              f"({(e.stderr or '').strip()[:200]})")
    return False


def main() -> int:
    br = branch()
    # Snapshot BEFORE the first reset, or the reset would discard exactly the
    # changes we're trying to save.
    snapshot = {path: read_json(path) for path in state_files()}
    if not snapshot:
        print("state save: no state files present")
        return 0

    for i in range(1, ATTEMPTS + 1):
        if attempt(snapshot, br):
            return 0
        print(f"  attempt {i}/{ATTEMPTS} failed")

    # Loud on purpose. The old code exited 0 here and that is how a live video
    # went missing from the dashboard for a day without anyone noticing.
    print(f"STATE SAVE FAILED after {ATTEMPTS} attempts — "
          f"this run's dashboard/no-repeat state was NOT persisted", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
