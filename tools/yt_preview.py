"""Renders a card WITH YouTube's interface mocked on top of it.

The card always looked good as a PNG — that's exactly why the bug shipped twice.
This puts the player controls, channel handle and title bar back over the frame so
what you're looking at is what a viewer looks at.

Run: python tools/yt_preview.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw  # noqa: E402

import card  # noqa: E402
import content  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "_ytpreview")


def overlay(png: str, out: str) -> str:
    """Paint YouTube's UI over a card, the way the platform does."""
    im = Image.open(png).convert("RGBA")
    ui = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ui)
    f = card._font("Anton-Regular.ttf", 34)

    # top: player controls (pause / volume / CC / settings / fullscreen)
    d.rectangle((0, 0, card.W, 125), fill=(20, 20, 20, 150))
    for i, x in enumerate((70, 170)):
        d.ellipse((x - 42, 22, x + 42, 106), fill=(230, 230, 230, 220))
    for x in (830, 920, 1010):
        d.ellipse((x - 34, 30, x + 34, 98), fill=(230, 230, 230, 220))

    # bottom: channel handle, video title, description — the block that ate the CTA
    d.rectangle((0, 1750, card.W, card.H), fill=(20, 20, 20, 150))
    d.ellipse((40, 1772, 104, 1836), fill=(240, 240, 240, 230))
    d.text((120, 1780), "@CoolDecide", font=f, fill=(255, 255, 255, 255))
    d.text((40, 1858), "Who Would WIN? Entire candy factory vs Whole theme park...",
           font=card._font("Anton-Regular.ttf", 30), fill=(235, 235, 235, 255))

    # right: like / comment / share rail (mobile app overlays this ON the video)
    for i, y in enumerate((1180, 1330, 1480, 1620)):
        d.ellipse((card.W - 130, y, card.W - 46, y + 84), fill=(240, 240, 240, 200))

    # the safe-area lines, so the margins are visible rather than implied
    d.line((0, card.SAFE_TOP, card.W, card.SAFE_TOP), fill=(0, 255, 90, 255), width=4)
    d.line((0, card.SAFE_BOTTOM, card.W, card.SAFE_BOTTOM), fill=(0, 255, 90, 255), width=4)

    im.alpha_composite(ui)
    im.convert("RGB").save(out, "PNG")
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for fmt in ("rank", "wyr", "trivia"):
        it = content.daily_item(fmt, "2026-07-16")
        card.set_topic_label("")
        raw = os.path.join(OUT, f"{fmt}_raw.png")
        card.render(it, raw, countdown=3)
        overlay(raw, os.path.join(OUT, f"{fmt}_asviewed.png"))
        card.render(it, raw, reveal=True)
        overlay(raw, os.path.join(OUT, f"{fmt}_reveal_asviewed.png"))
        print("  ", fmt, "->", it.a, "vs", it.b)
    print("\npreviews in", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
