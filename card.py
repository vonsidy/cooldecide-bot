"""Renders the 1080x1920 frames for a kids fun-Short.

Three states, so a video can go vote -> countdown -> reveal:
  render(item, out, countdown=3)          # options + a big "3" timer
  render(item, out, countdown=2 / 1)      # ticking down
  render(item, out, reveal=True)          # percentage bars fill in
"""
from __future__ import annotations
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONTS = os.path.join(os.path.dirname(__file__), "fonts")
EMOJI_FONT = "C:/Windows/Fonts/seguiemj.ttf"
A_COLOR = (255, 78, 82)     # warm red/pink
B_COLOR = (56, 132, 255)    # blue
GOLD = (255, 209, 74)
GREEN = (60, 210, 120)
INK = (12, 14, 26)
WHITE = (255, 255, 255)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _emoji(size: int) -> ImageFont.FreeTypeFont | None:
    try:
        return ImageFont.truetype(EMOJI_FONT, size)
    except OSError:
        return None


def _gradient(top: tuple, bottom: tuple) -> Image.Image:
    base = Image.new("RGB", (W, H), bottom)
    top_img = Image.new("RGB", (W, H), top)
    mask = Image.new("L", (1, H))
    for y in range(H):
        mask.putpixel((0, y), int(255 * (1 - y / H) ** 1.3))
    base.paste(top_img, (0, 0), mask.resize((W, H)))
    return base.convert("RGBA")


def _text_c(draw, cx, y, text, font, fill, max_w=None):
    if max_w:
        while draw.textlength(text, font=font) > max_w and font.size > 20:
            font = ImageFont.truetype(font.path, font.size - 2)
    w = draw.textlength(text, font=font)
    draw.text((cx - w / 2, y), text, font=font, fill=fill)
    return font


def _emoji_c(canvas, cx, y, ch, size):
    f = _emoji(size)
    if not f or not ch:
        return
    d = ImageDraw.Draw(canvas)
    try:
        w = d.textlength(ch, font=f)
        d.text((cx - w / 2, y), ch, font=f, embedded_color=True)
    except Exception:
        pass


def _panel(canvas, top_y, height, color, text, emoji, pct, reveal, winner, is_correct, factual):
    draw = ImageDraw.Draw(canvas)
    cx = W // 2
    # rounded panel
    dim = reveal and factual and not is_correct
    fill = tuple(int(c * (0.4 if dim else 1)) for c in color) + (255,)
    draw.rounded_rectangle((70, top_y, W - 70, top_y + height), radius=46, fill=fill)
    # emoji + option text
    _emoji_c(canvas, cx, top_y + 34, emoji, 150)
    tf = _text_c(draw, cx, top_y + 200, text.upper(), _font("Anton-Regular.ttf", 66), WHITE, max_w=W - 200)
    # percentage number + progress bar (revealed only)
    if reveal:
        num_y = top_y + 200 + tf.size + 12
        _text_c(draw, cx, num_y, f"{pct}%", _font("Anton-Regular.ttf", 96), WHITE)
        by0 = num_y + 108
        by1 = by0 + 34
        # dark track + bright fill, so the length reads at a glance
        draw.rounded_rectangle((130, by0, W - 130, by1), radius=17, fill=(0, 0, 0, 110))
        fillw = int((W - 260) * pct / 100)
        bar_col = GREEN if (factual and is_correct) else GOLD
        draw.rounded_rectangle((130, by0, 130 + max(fillw, 34), by1), radius=17, fill=bar_col + (255,))
        if factual and is_correct:
            _emoji_c(canvas, W - 158, top_y + 26, "✅", 74)
        if not factual and winner:
            _emoji_c(canvas, W - 158, top_y + 26, "👑", 74)


def render(item, out_path: str, countdown: int | None = None, reveal: bool = False) -> str:
    canvas = _gradient((92, 46, 168), (14, 12, 40))   # fun purple
    draw = ImageDraw.Draw(canvas)
    cx = W // 2
    factual = item.correct is not None
    a_win = item.a_pct >= item.b_pct

    # header
    import content
    _text_c(draw, cx, 58, content.format_label(item.fmt), _font("Anton-Regular.ttf", 82), GOLD, max_w=W - 60)

    _panel(canvas, 250, 560, A_COLOR, item.a, item.a_emoji, item.a_pct,
           reveal, a_win, item.correct == 0, factual)
    _panel(canvas, 1010, 560, B_COLOR, item.b, item.b_emoji, item.b_pct,
           reveal, not a_win, item.correct == 1, factual)

    # center chip: countdown number during the timer, "VS" during the vote, nothing on reveal
    if not reveal:
        chip = 150
        cy = 832
        badge = Image.new("RGBA", (chip, chip), (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge)
        bd.ellipse((0, 0, chip, chip), fill=INK + (255,), outline=GOLD + (255,), width=7)
        mid = str(countdown) if countdown is not None else "VS"
        mf = _font("Anton-Regular.ttf", 96 if countdown is not None else 66)
        mw = bd.textlength(mid, font=mf)
        bd.text((chip / 2 - mw / 2, chip / 2 - (70 if countdown is not None else 48)), mid, font=mf, fill=GOLD + (255,))
        canvas.alpha_composite(badge, (cx - chip // 2, cy))

    # footer
    draw.rounded_rectangle((cx - 420, 1730, cx + 420, 1850), radius=34, fill=GOLD)
    footer = "DID YOU GET IT?" if (reveal and factual) else ("WHAT DID YOU PICK?" if reveal else "COMMENT YOUR PICK")
    _text_c(draw, cx, 1752, footer, _font("Anton-Regular.ttf", 58), INK, max_w=800)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


if __name__ == "__main__":
    import content
    it = content.daily_item("wyr", "2026-07-16")
    render(it, "output/frame_vote.png", countdown=3)
    render(it, "output/frame_reveal.png", reveal=True)
    print("rendered vote+reveal for:", it.a, "vs", it.b, f"({it.a_pct}/{it.b_pct})")
