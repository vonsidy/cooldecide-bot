"""Push kids.json to the dashboard repo, so the site shows this channel's data.

The dashboard is served from a DIFFERENT repo (youtube-shorts-bot) — this bot has
its own repo and only shares the site. Nothing links them automatically, so
without this step the dashboard silently freezes at whatever was last copied
across by hand while the bot happily keeps posting.

Uses the Contents API rather than cloning: it's one small file, and cloning the
dashboard repo (with its videos and art) to change one line would be absurd.

Needs DASHBOARD_TOKEN — a fine-grained token scoped to youtube-shorts-bot with
Contents: read+write, and nothing else. Never the account-wide token: a secret
that can do anything is a secret that can lose everything.
"""
from __future__ import annotations
import base64
import json
import os
import urllib.error
import urllib.request

REPO = os.getenv("DASHBOARD_REPO", "vonsidy/youtube-shorts-bot")
REMOTE_PATH = "dashboard/kids.json"
LOCAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "kids.json")
UA = {"User-Agent": "cooldecide-bot/0.1"}


def _api(path: str, token: str, data: dict | None = None, method: str | None = None):
    req = urllib.request.Request(f"https://api.github.com/{path}", method=method, headers=UA)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    body = None
    if data is not None:
        req.add_header("Content-Type", "application/json")
        body = json.dumps(data).encode()
    with urllib.request.urlopen(req, body, timeout=30) as r:
        raw = r.read()
        return (json.loads(raw) if raw else {}), r.status


def sync() -> bool:
    """Copy the local kids.json to the dashboard repo. True if it pushed."""
    token = os.getenv("DASHBOARD_TOKEN", "").strip()
    if not token:
        print("  (no DASHBOARD_TOKEN — dashboard not updated)")
        return False
    if not os.path.exists(LOCAL_PATH):
        print("  (no local kids.json — nothing to sync)")
        return False

    local = open(LOCAL_PATH, "rb").read()

    sha = None
    try:
        cur, _ = _api(f"repos/{REPO}/contents/{REMOTE_PATH}", token)
        sha = cur.get("sha")
        remote = base64.b64decode(cur.get("content", "")).decode("utf-8", "replace")
        if remote == local.decode("utf-8", "replace"):
            print("  dashboard already up to date")
            return False               # identical: don't make an empty commit
    except urllib.error.HTTPError as e:
        if e.code != 404:              # 404 = first push, anything else is real
            print(f"  (dashboard read failed: {e.code} — skipping)")
            return False

    payload = {
        "message": "Update CoolDecide data [skip ci]",
        "content": base64.b64encode(local).decode(),
    }
    if sha:
        payload["sha"] = sha           # required, or GitHub rejects the overwrite
    try:
        _, status = _api(f"repos/{REPO}/contents/{REMOTE_PATH}", token, payload, method="PUT")
        print(f"  dashboard updated ({status})")
        return True
    except urllib.error.HTTPError as e:
        # Never fail the run over the dashboard — the video is already posted, and
        # a stale board is a cosmetic problem. 409 = someone else wrote first;
        # the next check-in picks it up.
        print(f"  (dashboard push failed: {e.code} {e.reason} — video is fine)")
        return False


if __name__ == "__main__":
    sync()
