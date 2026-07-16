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
# Bright, playful, sticker-style palette — nothing dark.
BG_TOP = (90, 214, 255)     # bright sky cyan
BG_BOT = (120, 156, 255)    # cheerful blue
A_COLOR = (255, 90, 110)    # coral red
B_COLOR = (124, 92, 255)    # bright purple
GOLD = (255, 209, 64)
GREEN = (54, 214, 122)
NAVY = (28, 40, 92)         # dark text for contrast on bright backgrounds
INK = (20, 24, 48)
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


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_c(draw, cx, y, text, font, fill, max_w=None):
    if max_w:
        while draw.textlength(text, font=font) > max_w and font.size > 20:
            font = ImageFont.truetype(font.path, font.size - 2)
    w = draw.textlength(text, font=font)
    draw.text((cx - w / 2, y), text, font=font, fill=fill)
    return font


def _emoji_c(canvas, cx, y, ch, size):
    """Draw an emoji truly centred on cx, inside a `size` box at y.

    Font metrics CANNOT be trusted here. Many emoji carry an invisible variation
    selector (U+FE0F) — 🏖️ is U+1F3D6 + U+FE0F — and PIL counts that zero-width
    character as a second glyph. textbbox reported 🏖️ as 852px wide when its real
    ink was 306px, which centred it 213px to the LEFT. (🍕 has no selector, so it
    looked fine — which is why this hid for so long.)

    So: draw onto a scratch layer, find the ACTUAL ink with getbbox(), and place
    that. Correct for any emoji, selector or not.
    """
    f = _emoji(size)
    if not f or not ch:
        return
    try:
        pad = int(size * 2)
        tmp = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((pad // 2, pad // 2), ch, font=f, embedded_color=True)
        box = tmp.getbbox()
        if not box:
            return
        ink = tmp.crop(box)
        ink.thumbnail((size, size), Image.LANCZOS)   # also normalises the size
        canvas.alpha_composite(ink, (int(cx - ink.width / 2),
                                     int(y + (size - ink.height) / 2)))
    except Exception:
        pass


def _shadow_text(draw, cx, y, text, font, fill, shadow=NAVY, max_w=None, off=5):
    if max_w:
        while draw.textlength(text, font=font) > max_w and font.size > 20:
            font = ImageFont.truetype(font.path, font.size - 2)
    w = draw.textlength(text, font=font)
    draw.text((cx - w / 2 + off, y + off), text, font=font, fill=shadow)
    draw.text((cx - w / 2, y), text, font=font, fill=fill)
    return font


# Drop real images (game logos, etc.) into assets/images/ named by the stem below;
# an option whose text contains the keyword uses that picture instead of the emoji.
IMAGES = os.path.join(os.path.dirname(__file__), "assets", "images")
IMAGE_KEYS = [
    ("minecraft", "minecraft"), ("roblox", "roblox"), ("fortnite", "fortnite"),
    ("v-bucks", "vbucks"), ("robux", "robux"), ("youtube", "youtube"), ("tiktok", "tiktok"),
    ("playstation", "playstation"), ("xbox", "xbox"), ("marvel", "marvel"), ("dc", "dc"),
]


def _image_for(option_text: str):
    t = option_text.lower()
    for sub, stem in IMAGE_KEYS:
        if sub in t:
            for ext in ("png", "jpg", "jpeg", "webp"):
                p = os.path.join(IMAGES, f"{stem}.{ext}")
                if os.path.exists(p):
                    return p
    return None


def _rounded(im: Image.Image, radius: int = 26) -> Image.Image:
    """Round a photo's corners so it reads as part of the card, not pasted on."""
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1),
                                           radius=radius, fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out


def photo_for(option_text: str) -> str | None:
    """A curated local file or a reviewed public-domain photo, else None."""
    path = _image_for(option_text)
    if path:
        return path
    try:
        import images
        return images.fetch(option_text)
    except Exception:  # noqa: BLE001 - offline etc: caller falls back to emoji
        return None


def _picture(canvas, cx, y, size, option_text, emoji, path=None):
    """Art for an option, centred in a `size`-tall box: photo if given, else emoji."""
    if path:
        try:
            im = Image.open(path).convert("RGBA")
            im.thumbnail((min(W - 260, int(size * 2.4)), size), Image.LANCZOS)
            if os.path.dirname(path).endswith("auto"):
                im = _rounded(im)          # photos; curated logos stay as-is
            canvas.alpha_composite(im, (int(cx - im.width / 2),
                                        int(y + (size - im.height) / 2)))
            return
        except Exception:  # noqa: BLE001
            pass
    _emoji_c(canvas, cx, y, emoji, size)


def _panel(canvas, top_y, height, color, text, emoji, pct, reveal, winner, is_correct,
           factual, photo=None):
    draw = ImageDraw.Draw(canvas)
    cx = W // 2
    # bright rounded panel with a thick white "sticker" border
    dim = reveal and factual and not is_correct
    fill = tuple(int(c + (255 - c) * 0.45) for c in color) if dim else color
    draw.rounded_rectangle((60, top_y, W - 60, top_y + height), radius=52, fill=WHITE)
    draw.rounded_rectangle((72, top_y + 12, W - 72, top_y + height - 12), radius=44, fill=fill + (255,))

    has_pic = bool(emoji)
    # The picture is the thing you scroll past or stop for, so it gets the room:
    # at 200px it floated in a 560px panel looking like an afterthought. Shrinks
    # on the reveal to make way for the % and the bar.
    em = (200 if reveal else 310) if has_pic else 0
    gap = 16 if has_pic else 0
    tsize = 62 if has_pic else 88                      # answer-only options (trivia) read bigger
    tf = _font("Anton-Regular.ttf", tsize)
    while draw.textlength(text.upper(), font=tf) > W - 210 and tf.size > 30:
        tf = _font("Anton-Regular.ttf", tf.size - 2)
    num_sz, num_gap, bar_h, bar_gap = 92, 34, 38, 30    # generous gaps so nothing overlaps
    # vertically centre the whole content block inside the panel. Factual reveals
    # carry no bar (see below), so they're shorter.
    extra = 0
    if reveal:
        extra = num_gap + num_sz + (0 if factual else bar_gap + bar_h)
    block = em + gap + tf.size + extra
    y = top_y + (height - block) // 2

    if has_pic:
        _picture(canvas, cx, y, em, text, emoji, photo)
    _shadow_text(draw, cx, y + em + gap, text.upper(), tf, WHITE, off=4, max_w=W - 210)

    if reveal and factual:
        # A question with a RIGHT ANSWER gets no percentage. The number is made up,
        # and on a kids channel a big "83%" next to the wrong answer teaches the
        # wrong thing — it read "83% said 5 continents" / "66% said blue+yellow=
        # purple". The answer itself is the payoff here.
        _shadow_text(draw, cx, y + em + gap + tf.size + num_gap,
                     "CORRECT!" if is_correct else "NOPE",
                     _font("Anton-Regular.ttf", 76), WHITE, off=5)
    elif reveal:
        # Opinion formats keep it: "most people picked the dragon" is a claim about
        # taste, so it isn't asserting anything false — and it's the argument fuel.
        num_y = y + em + gap + tf.size + num_gap
        _shadow_text(draw, cx, num_y, f"{pct}%", _font("Anton-Regular.ttf", num_sz), WHITE, off=5)
        by0 = num_y + num_sz + bar_gap
        by1 = by0 + bar_h
        draw.rounded_rectangle((140, by0, W - 140, by1), radius=bar_h // 2, fill=(255, 255, 255, 120))
        fillw = int((W - 280) * pct / 100)
        draw.rounded_rectangle((140, by0, 140 + max(fillw, bar_h), by1), radius=bar_h // 2, fill=GOLD + (255,))
    # winner crown / correct check pinned to the panel corner
    if reveal and factual and is_correct:
        _emoji_c(canvas, W - 172, top_y + 30, "✅", 80)
    if reveal and not factual and winner:
        _emoji_c(canvas, W - 172, top_y + 30, "👑", 80)


def render(item, out_path: str, countdown: int | None = None, reveal: bool = False) -> str:
    canvas = _gradient(BG_TOP, BG_BOT)   # bright, cheerful
    draw = ImageDraw.Draw(canvas)
    cx = W // 2
    factual = item.correct is not None
    a_win = item.a_pct >= item.b_pct

    # header — the format label, except trivia shows the actual question so the
    # two answer options make sense.
    import content
    if item.fmt == "trivia":
        _shadow_text(draw, cx, 40, "QUIZ TIME", _font("Anton-Regular.ttf", 46), GOLD, off=4)
        qfont = _font("Anton-Regular.ttf", 62)
        lines = _wrap(draw, item.prompt.upper(), qfont, W - 90)[:2]
        for i, ln in enumerate(lines):
            _shadow_text(draw, cx, 104 + i * 66, ln, qfont, WHITE, off=4)
    else:
        _shadow_text(draw, cx, 56, content.format_label(item.fmt), _font("Anton-Regular.ttf", 84), WHITE, off=6, max_w=W - 50)

    # Photos are all-or-nothing per round: a real photo beside a cartoon emoji
    # looks like a mistake, so unless BOTH sides have one, both use the emoji.
    a_photo, b_photo = photo_for(item.a), photo_for(item.b)
    if not (a_photo and b_photo):
        a_photo = b_photo = None

    _panel(canvas, 250, 560, A_COLOR, item.a, item.a_emoji, item.a_pct,
           reveal, a_win, item.correct == 0, factual, a_photo)
    _panel(canvas, 1010, 560, B_COLOR, item.b, item.b_emoji, item.b_pct,
           reveal, not a_win, item.correct == 1, factual, b_photo)

    # center chip: bright white badge with a colored ring + big number
    if not reveal:
        chip = 158
        cy = 828
        badge = Image.new("RGBA", (chip, chip), (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge)
        ring = GOLD if countdown is None else (255, 90, 110)
        bd.ellipse((0, 0, chip, chip), fill=WHITE + (255,), outline=ring + (255,), width=10)
        mid = str(countdown) if countdown is not None else "VS"
        mf = _font("Anton-Regular.ttf", 100 if countdown is not None else 66)
        mw = bd.textlength(mid, font=mf)
        bd.text((chip / 2 - mw / 2, chip / 2 - (72 if countdown is not None else 48)), mid, font=mf, fill=NAVY + (255,))
        canvas.alpha_composite(badge, (cx - chip // 2, cy))

    # footer pill
    draw.rounded_rectangle((cx - 430, 1728, cx + 430, 1856), radius=40, fill=WHITE)
    draw.rounded_rectangle((cx - 418, 1740, cx + 418, 1844), radius=34, fill=GOLD)
    # The ask is physical, not verbal: point at the screen. It's an action a kid
    # can do instantly while watching, so it reads as "play along" rather than a
    # chore — and it keeps hands/eyes on the video instead of in the comments.
    footer = "DID YOU GET IT?" if (reveal and factual) else ("DID YOU PICK IT?" if reveal else "POINT AT YOUR PICK!")
    _text_c(draw, cx, 1758, footer, _font("Anton-Regular.ttf", 60), NAVY, max_w=800)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


if __name__ == "__main__":
    import content
    it = content.daily_item("wyr", "2026-07-16")
    render(it, "output/frame_vote.png", countdown=3)
    render(it, "output/frame_reveal.png", reveal=True)
    print("rendered vote+reveal for:", it.a, "vs", it.b, f"({it.a_pct}/{it.b_pct})")
