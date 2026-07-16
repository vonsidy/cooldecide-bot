"""Central settings for the kids fun-Shorts bot.

Reads from environment first, then a local .env (gitignored). Kept flat (no
package) to match the rest of this project.
"""
from __future__ import annotations
import os

_HERE = os.path.dirname(__file__)


def _from_env_file(key: str) -> str | None:
    env = os.path.join(_HERE, ".env")
    if os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def get(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key) or _from_env_file(key) or default


# --- YouTube upload -----------------------------------------------------------
# Same Google Cloud project/OAuth client as the Nyxtold bot, but a SEPARATE token
# (this bot posts to its own new channel). Files are gitignored.
YT_CLIENT_SECRETS = os.path.join(_HERE, "client_secret.json")
YT_TOKEN_FILE = os.path.join(_HERE, "yt_token.json")

# unlisted while testing; flip to "public" once you're happy with the output.
YT_PRIVACY = get("YT_PRIVACY", "unlisted")

# 24 = Entertainment. Good fit for fun quiz/would-you-rather Shorts.
YT_CATEGORY_ID = get("YT_CATEGORY_ID", "24")

# COPPA / "Made for Kids": if the channel is directed at children, YouTube
# requires this True — but that DISABLES comments, notifications, personalized
# ads (lower revenue) and some features. Many kid-APPEAL channels aimed at a
# general/family audience mark it False. This is YOUR call (see the notes I gave
# you); default False keeps engagement features on. Override with MADE_FOR_KIDS=1.
MADE_FOR_KIDS = get("MADE_FOR_KIDS", "0") == "1"

# Safety valve: never upload unless explicitly enabled (env or --upload flag).
UPLOAD = get("UPLOAD", "0") == "1"
