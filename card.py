"""Renders the 1080x1920 frames for a kids fun-Short.

Three states, so a video can go vote -> countdown -> reveal:
  render(item, out, countdown=3)          # options + a big "3" timer
  render(item, out, countdown=2 / 1)      # ticking down
  render(item, out, reveal=True)          # percentage bars fill in
"""
from __future__ import annotations
import os
import re

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONTS = os.path.join(os.path.dirname(__file__), "fonts")

# The emoji is the universal fallback whenever a card has no artwork — the design
# leans on it as "always on-topic and always safe" (see photo_for / images.py). It
# therefore has to resolve on the box that actually RENDERS, and that box is the
# Linux CI runner, not a Windows desktop. A hardcoded C:/Windows path silently
# returned no font in the cloud, so _emoji() was None on every call and every
# art-less round shipped a BLANK panel — no picture and no emoji. Pick the first
# emoji font that exists on THIS OS instead.
_EMOJI_FONT_CANDIDATES = (
    "C:/Windows/Fonts/seguiemj.ttf",                       # Windows
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",   # Debian/Ubuntu (CI runner)
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",            # Arch/Fedora
    "/System/Library/Fonts/Apple Color Emoji.ttc",         # macOS
)
EMOJI_FONT = next((p for p in _EMOJI_FONT_CANDIDATES if os.path.exists(p)), "")

# YouTube stamps its OWN interface over the video, and we don't get a say: player
# controls across the top, the channel handle + video title + description across
# the bottom. Anything drawn there is invisible to the viewer no matter how good
# it looks in the PNG — the first cards put the format name under the pause button
# and "POINT AT YOUR PICK!" under the video title, so the two things the video is
# actually asking of you were the two things nobody could read.
# Measured off the live desktop player (controls end ~y125, title block starts
# ~y1750); the mobile app stacks handle + title + description and reaches higher,
# so these keep a wide margin on both. Empty margin is cheap; hidden content isn't.
# 160 vs a measured ~125: enough clearance to be safe without starving the panels,
# which have to fit a picture AND the %+bar between these two lines.
SAFE_TOP = 160
SAFE_BOTTOM = 1660
FOOTER_H = 120
VS_GAP = 200        # gap between panels — must clear the countdown chip (max 198)
FOOTER_GAP = 36     # air between panel B and the CTA pill, so it reads as its own thing


def _layout(header_bottom: int) -> tuple[int, int, int, int]:
    """Fit header → panel → chip → panel → footer inside the safe box.

    Computed, not hardcoded, because the header's height varies: trivia prints the
    whole question, so its panels must start lower than a two-word format label's.
    Returns (panel_a_top, panel_height, panel_b_top, footer_top).
    """
    # -10 so the pill's bottom edge CLEARS the line rather than landing on it:
    # rounded_rectangle draws inclusive of its end coordinate, so a pill ending at
    # exactly SAFE_BOTTOM still puts a lit row inside the reserved band.
    footer_top = SAFE_BOTTOM - FOOTER_H - 10
    a_top = header_bottom + 16
    panel_h = ((footer_top - FOOTER_GAP - a_top) - VS_GAP) // 2
    return a_top, panel_h, a_top + panel_h + VS_GAP, footer_top
# Bright, playful, sticker-style palette — nothing dark.
BG_TOP = (90, 214, 255)     # bright sky cyan
BG_BOT = (120, 156, 255)    # cheerful blue
A_COLOR = (255, 90, 110)    # coral red
B_COLOR = (124, 92, 255)    # bright purple

# A different skin per video, so two Shorts in a row don't look like the same one
# twice. The LAYOUT never changes — only the colours — so the channel still reads
# as one thing. Each palette keeps the two panels clearly different from each
# other and dark enough for white text to hold up.
PALETTES = {
    "sky":    ((90, 214, 255), (120, 156, 255), (255, 90, 110), (124, 92, 255)),
    "sunset": ((255, 168, 92), (255, 108, 148), (94, 86, 214), (232, 74, 106)),
    "mint":   ((116, 235, 198), (74, 186, 236), (255, 104, 126), (92, 104, 220)),
    "candy":  ((198, 148, 255), (255, 138, 200), (238, 72, 108), (72, 132, 236)),
    "ocean":  ((84, 222, 236), (66, 138, 230), (240, 118, 74), (140, 88, 246)),
    "sunny":  ((255, 214, 88), (255, 146, 92), (74, 116, 240), (236, 70, 116)),
    "grape":  ((160, 136, 255), (108, 118, 246), (255, 122, 78), (46, 190, 160)),
}


# Set per video by run.py; blank means "don't claim a theme" (see content.is_themed).
TOPIC_LABEL = ""


def set_topic_label(label: str) -> None:
    global TOPIC_LABEL
    TOPIC_LABEL = label or ""


def set_palette(name: str) -> str:
    """Swap the video's colour scheme. Unknown name falls back to the default."""
    global BG_TOP, BG_BOT, A_COLOR, B_COLOR
    BG_TOP, BG_BOT, A_COLOR, B_COLOR = PALETTES.get(name, PALETTES["sky"])
    return name if name in PALETTES else "sky"


# Each format sits at a different point in the rotation, so same-day videos can't
# land on the same skin.
_FMT_OFFSET = {"wyr": 0, "this_or_that": 1, "rank": 2, "higher_lower": 3, "trivia": 4}


def palette_for(date_iso: str, fmt: str = "") -> str:
    """Pick a palette deterministically — a re-render of a video looks identical.

    A ROTATION, not a hash. Hashing collided badly: it gave three identical videos
    on one day (mint/mint/mint) and repeats four days apart. Stepping by 3 through
    7 palettes (coprime, so it visits all 7 before repeating) means consecutive days
    are always different, and the per-format offset separates same-day videos.
    """
    import datetime as _dt
    keys = sorted(PALETTES)
    try:
        day = _dt.date.fromisoformat(str(date_iso)[:10]).toordinal()
    except ValueError:
        day = sum(ord(c) for c in str(date_iso))
    return keys[(day * 3 + _FMT_OFFSET.get(fmt, 0)) % len(keys)]
GOLD = (255, 209, 64)
GREEN = (54, 214, 122)
NAVY = (28, 40, 92)         # dark text for contrast on bright backgrounds
INK = (20, 24, 48)
WHITE = (255, 255, 255)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _emoji(size: int) -> ImageFont.FreeTypeFont | None:
    if not EMOJI_FONT:
        return None
    try:
        return ImageFont.truetype(EMOJI_FONT, size)
    except OSError:
        # Colour-bitmap emoji fonts (NotoColorEmoji, Apple Color Emoji) ship only
        # fixed strike sizes and PIL rejects any other — NotoColorEmoji exposes 109.
        # The sole caller (_emoji_c) rescales the rendered glyph to the size it
        # needs, so loading at a valid strike and letting it resize is correct.
        for strike in (109, 128, 137, 160, 96, 64):
            try:
                return ImageFont.truetype(EMOJI_FONT, strike)
            except OSError:
                continue
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
        # Scale the ink to FILL the box, up or down, preserving aspect ratio.
        # thumbnail() only ever shrinks, so on Linux — where NotoColorEmoji renders at a
        # fixed ~120px strike — a big panel showed a tiny emoji marooned in empty space
        # (a vote card's 315px slot was only 38% filled). This fills the space the
        # fallback is meant to occupy; on Windows (scalable font) the glyph already
        # matches `size`, so the scale is ~1 and nothing changes.
        scale = size / max(ink.width, ink.height)
        ink = ink.resize((max(1, round(ink.width * scale)),
                          max(1, round(ink.height * scale))), Image.LANCZOS)
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
    ("playstation", "playstation"), ("xbox", "xbox"), ("marvel", "marvel"),
    ("lego", "lego"), ("nerf", "nerf"),
    # "dc" last, and it's a 2-letter string that appears inside ordinary words —
    # so it must only match on its own (see _image_for).
    ("dc", "dc"),
]


def _image_for(option_text: str):
    """The curated logo for this option, if one is on disk.

    Matched on WORD boundaries, not raw substring: "dc" is two letters and hides
    inside ordinary words — "sandcastle" contains "dc" and would have pulled up
    the DC Comics logo.
    """
    t = option_text.lower()
    for sub, stem in IMAGE_KEYS:
        if re.search(rf"(?<![a-z]){re.escape(sub)}(?![a-z])", t):
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


def _chip(im: Image.Image, pad: int = 20, radius: int = 24) -> Image.Image:
    """Sit a logo on a white rounded chip.

    Brand logos are usually flat art on transparency in whatever colour the brand
    uses — Fortnite's wordmark is BLACK, which is invisible on the coral panel.
    A white chip guarantees contrast no matter what the logo's colours are.
    """
    w, h = im.width + pad * 2, im.height + pad * 2
    chip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(chip).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                                           fill=WHITE + (255,))
    chip.alpha_composite(im, (pad, pad))
    return chip


# Options where a REAL image beats generated art. An illustrator can draw an idea,
# but it can only APPROXIMATE a specific real thing — asked for "Minecraft" it
# invents generic blocky mush, and for "the Eiffel Tower" it draws *an* iron tower.
# Brands and real landmarks therefore prefer a photo/logo; everything else is
# better generated (one consistent style, and it can picture abstract options).
REAL_FIRST = ("minecraft", "roblox", "fortnite", "playstation", "xbox", "tiktok",
              "youtube", "marvel", "dc", "eiffel", "everest", "school bus",
              "lego", "nerf")


def _prefers_real(option_text: str) -> bool:
    t = option_text.lower()
    return any(k in t for k in REAL_FIRST)


def photo_for(option_text: str, hint: str | None = None) -> str | None:
    """Best art for an option.

    Order: a curated local logo, then a real photo IF this is a specific real
    thing, then generated cartoon art, then a real photo as a last resort.
    Returning None means the caller falls back to the emoji.
    """
    path = _image_for(option_text)          # hand-placed logo files win outright
    if path:
        return path

    def _real():
        try:
            import images
            return images.fetch(option_text)
        except Exception:  # noqa: BLE001
            return None

    if _prefers_real(option_text):
        path = _real()
        if path:
            return path
    try:
        import art
        return art.fetch(option_text, hint)
    except Exception:  # noqa: BLE001
        return None
    # NOTE: deliberately no stock-photo fallback here. It put a cartoon pizza next
    # to a PHOTOGRAPH of ice cream on the same card — the all-or-nothing rule only
    # checks that art exists, not that it's the same kind. If generation hasn't run
    # for an option yet, the emoji is the honest fallback; a style clash looks worse
    # than an emoji does. Stock photos survive only for REAL_FIRST terms above,
    # where a real landmark genuinely beats a drawing.


# Image models cannot count. Asked to illustrate the answer "7" the generator drew
# a family of three; for "5" it drew one kid. Sat next to the answer, that reads as
# "the answer is a family" — actively worse than no picture, and on a quiz card it
# teaches the wrong thing. A numeric answer IS its own visual, so it gets the
# big-text treatment instead.
_NUMERIC = re.compile(r"^[\s\d.,/-]+$")


def _is_number(text: str) -> bool:
    return bool(text) and bool(_NUMERIC.match(text))


def _picture(canvas, cx, y, size, option_text, emoji, path=None):
    """Art for an option, centred in a `size`-tall box: photo if given, else emoji."""
    if path:
        try:
            im = Image.open(path).convert("RGBA")
            parent = os.path.basename(os.path.dirname(path))
            if parent == "images":                     # a brand logo
                im.thumbnail((min(W - 300, int(size * 2.0)), size - 40), Image.LANCZOS)
                im = _chip(im)
            else:
                im.thumbnail((min(W - 260, int(size * 2.4)), size), Image.LANCZOS)
                # Photos and generated art both arrive as hard rectangles (the art
                # comes on its own white background), which reads as a box stuck on
                # the panel. Rounding makes it a sticker.
                if parent in ("auto", "art"):
                    im = _rounded(im, radius=34)
            canvas.alpha_composite(im, (int(cx - im.width / 2),
                                        int(y + (size - im.height) / 2)))
            return
        except Exception:  # noqa: BLE001
            pass
    _emoji_c(canvas, cx, y, emoji, size)


def _panel(canvas, top_y, height, color, text, emoji, pct, reveal, winner, is_correct,
           factual, photo=None, grow=1.0):
    # NB: `grow` (the count-up 0..1), NOT `fill` — this function already uses a
    # local `fill` for the panel's RGB, which silently shadowed the parameter.
    draw = ImageDraw.Draw(canvas)
    cx = W // 2
    # bright rounded panel with a thick white "sticker" border
    dim = reveal and factual and not is_correct
    fill = tuple(int(c + (255 - c) * 0.45) for c in color) if dim else color
    draw.rounded_rectangle((60, top_y, W - 60, top_y + height), radius=52, fill=WHITE)
    draw.rounded_rectangle((72, top_y + 12, W - 72, top_y + height - 12), radius=44, fill=fill + (255,))

    # A photo counts as art even with no emoji — trivia rows carry no emoji at all
    # ("Cheetah"/"Lion"), so keying this off the emoji alone left quiz cards bare.
    has_pic = bool(emoji) or bool(photo)
    gap = 16 if has_pic else 0
    # With no picture the ANSWER is the visual, so it takes the panel: a numeric
    # quiz answer at a flat 88px sat marooned in the middle of an empty card. Scaled
    # to the panel rather than fixed, since the panel height flexes; the shrink loop
    # below pulls it back for anything long.
    tsize = 62 if has_pic else int(height * 0.32)
    tf = _font("Anton-Regular.ttf", tsize)
    while draw.textlength(text.upper(), font=tf) > W - 210 and tf.size > 30:
        tf = _font("Anton-Regular.ttf", tf.size - 2)
    # bar_gap is measured from the % text's BOX, and Anton's digits don't fill it,
    # so the visual gap always lands tighter than the number suggests — hence the
    # roomy value here.
    num_sz, num_gap, bar_h, bar_gap = 92, 34, 38, 60
    # Factual reveals carry no bar (see below), so they're shorter.
    extra = 0
    if reveal:
        extra = num_gap + num_sz + (0 if factual else bar_gap + bar_h)

    # Everything is centred inside the panel's INNER area — the white sticker border
    # eats 12px a side, and centring against the outer edge drew the % bar straight
    # through it. The picture takes what's left after the text and the %+bar have
    # been paid for, rather than a fixed size: the panel height now flexes to fit
    # YouTube's safe area, and a hardcoded 200px reveal picture overflowed the
    # shorter panel that leaves.
    pad = 24                       # 12px border + 12px of actual air below the bar
    inner = height - pad * 2
    # The picture is the thing you scroll past or stop for, so it gets the room that
    # remains: at 200px it floated in a 560px panel looking like an afterthought.
    em = max(0, min(int(height * (0.34 if reveal else 0.63)),
                    inner - gap - tf.size - extra)) if has_pic else 0
    block = em + gap + tf.size + extra
    y = top_y + pad + (inner - block) // 2

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
        # `grow` (0..1) drives the count-up: the bar grows and the number climbs to
        # the real value, so the result is an EVENT rather than a fact that was
        # simply already on screen.
        shown = int(round(pct * grow))
        num_y = y + em + gap + tf.size + num_gap
        _shadow_text(draw, cx, num_y, f"{shown}%", _font("Anton-Regular.ttf", num_sz), WHITE, off=5)
        by0 = num_y + num_sz + bar_gap
        by1 = by0 + bar_h
        draw.rounded_rectangle((140, by0, W - 140, by1), radius=bar_h // 2, fill=(255, 255, 255, 120))
        fillw = int((W - 280) * shown / 100)
        if fillw > 2:
            draw.rounded_rectangle((140, by0, 140 + max(fillw, bar_h), by1),
                                   radius=bar_h // 2, fill=GOLD + (255,))
    # winner crown / correct check pinned to the panel corner
    if reveal and factual and is_correct:
        _emoji_c(canvas, W - 172, top_y + 30, "✅", 80)
    # Crown only once the count-up has landed — showing it at 24% crowns the winner
    # before the numbers finish climbing, which gives the result away.
    if reveal and not factual and winner and grow >= 0.999:
        _emoji_c(canvas, W - 172, top_y + 30, "👑", 80)


def outro(item, out_path: str) -> str:
    """The end card.

    The video used to just stop on the last reveal, leaving a dead beat with the
    answer sitting there. That second is the most valuable one in the video — the
    viewer has just been proven right or wrong and actually has something to say —
    so it asks for the comment instead of wasting it.
    """
    canvas = _gradient(BG_TOP, BG_BOT)
    draw = ImageDraw.Draw(canvas)
    cx = W // 2
    factual = item.correct is not None

    head = "HOW MANY" if factual else "WHICH ONE"
    line2 = "DID YOU GET?" if factual else "DID YOU PICK?"

    # big playful headline
    _shadow_text(draw, cx, 470, head, _font("Anton-Regular.ttf", 138), WHITE, off=7, max_w=W - 90)
    _shadow_text(draw, cx, 620, line2, _font("Anton-Regular.ttf", 138), GOLD, off=7, max_w=W - 90)

    # the ask, in a fat pill
    draw.rounded_rectangle((cx - 470, 880, cx + 470, 1050), radius=54, fill=WHITE)
    draw.rounded_rectangle((cx - 456, 894, cx + 456, 1036), radius=46, fill=A_COLOR + (255,))
    _text_c(draw, cx, 928, "COMMENT BELOW!", _font("Anton-Regular.ttf", 84), WHITE, max_w=860)

    _emoji_c(canvas, cx, 1120, "👇", 210)

    draw.rounded_rectangle((cx - 400, 1420, cx + 400, 1560), radius=44, fill=WHITE)
    draw.rounded_rectangle((cx - 388, 1432, cx + 388, 1548), radius=38, fill=GOLD)
    _text_c(draw, cx, 1454, "FOLLOW FOR MORE", _font("Anton-Regular.ttf", 66), NAVY, max_w=740)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


def render(item, out_path: str, countdown: int | None = None, reveal: bool = False,
           grow: float = 1.0) -> str:
    canvas = _gradient(BG_TOP, BG_BOT)   # bright, cheerful
    draw = ImageDraw.Draw(canvas)
    cx = W // 2
    factual = item.correct is not None
    a_win = item.a_pct >= item.b_pct

    # header — the format label, except trivia shows the actual question so the
    # two answer options make sense.
    import content
    if item.fmt == "trivia":
        _shadow_text(draw, cx, SAFE_TOP, "QUIZ TIME", _font("Anton-Regular.ttf", 46), GOLD, off=4)
        qfont = _font("Anton-Regular.ttf", 62)
        lines = _wrap(draw, item.prompt.upper(), qfont, W - 90)[:2]
        for i, ln in enumerate(lines):
            _shadow_text(draw, cx, SAFE_TOP + 64 + i * 66, ln, qfont, WHITE, off=4)
        head_bot = SAFE_TOP + 64 + len(lines) * 66
    else:
        label = content.format_label(item.fmt)
        if TOPIC_LABEL:
            # The topic is the video's identity, so it goes above the format name:
            # "FOOD EDITION / WOULD YOU RATHER".
            _shadow_text(draw, cx, SAFE_TOP, TOPIC_LABEL, _font("Anton-Regular.ttf", 46),
                         GOLD, off=4, max_w=W - 90)
            _shadow_text(draw, cx, SAFE_TOP + 58, label, _font("Anton-Regular.ttf", 84), WHITE,
                         off=6, max_w=W - 50)
            head_bot = SAFE_TOP + 154
        else:
            _shadow_text(draw, cx, SAFE_TOP + 22, label, _font("Anton-Regular.ttf", 84), WHITE,
                         off=6, max_w=W - 50)
            head_bot = SAFE_TOP + 118

    a_top, panel_h, b_top, footer_top = _layout(head_bot)

    # All-or-nothing per round: one side in artwork and the other in emoji looks
    # like a mistake, so unless BOTH sides have art, both fall back to the emoji.
    a_photo = photo_for(item.a, getattr(item, "a_art", "") or None)
    b_photo = photo_for(item.b, getattr(item, "b_art", "") or None)
    if not (a_photo and b_photo):
        a_photo = b_photo = None

    a_emoji, b_emoji = item.a_emoji, item.b_emoji
    if _is_number(item.a) or _is_number(item.b):
        a_photo = b_photo = None            # see _is_number: nothing can draw "7"
        a_emoji = b_emoji = ""

    _panel(canvas, a_top, panel_h, A_COLOR, item.a, a_emoji, item.a_pct,
           reveal, a_win, item.correct == 0, factual, a_photo, grow)
    _panel(canvas, b_top, panel_h, B_COLOR, item.b, b_emoji, item.b_pct,
           reveal, not a_win, item.correct == 1, factual, b_photo, grow)

    # center chip: bright white badge with a colored ring + big number
    if not reveal:
        # The timer ESCALATES: it grows and heats up green -> gold -> red as it
        # runs out. A fixed grey 3-2-1 is just a delay; this is a clock running
        # down on you, which is what makes you commit to a side before it lands.
        ramp = {3: (GREEN, 158), 2: (GOLD, 176), 1: ((255, 60, 80), 198)}
        ring, chip = ramp.get(countdown, (GOLD, 158))
        cy = a_top + panel_h + (VS_GAP - chip) // 2   # centred in the gap, whatever it grows to
        badge = Image.new("RGBA", (chip, chip), (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge)
        bd.ellipse((0, 0, chip, chip), fill=WHITE + (255,), outline=ring + (255,),
                   width=10 + (0 if countdown is None else (3 - countdown) * 3))
        mid = str(countdown) if countdown is not None else "VS"
        sz = int(chip * 0.63) if countdown is not None else 66
        mf = _font("Anton-Regular.ttf", sz)
        mw = bd.textlength(mid, font=mf)
        bd.text((chip / 2 - mw / 2, chip / 2 - (sz * 0.72 if countdown is not None else 48)),
                mid, font=mf, fill=(ring if countdown == 1 else NAVY) + (255,))
        canvas.alpha_composite(badge, (cx - chip // 2, cy))

    # footer pill — sits ABOVE SAFE_BOTTOM. It used to run to y1856, straight under
    # the video title YouTube prints over every Short, so the one instruction the
    # video gives was unreadable on the platform it was made for.
    draw.rounded_rectangle((cx - 430, footer_top, cx + 430, footer_top + FOOTER_H),
                           radius=40, fill=WHITE)
    draw.rounded_rectangle((cx - 418, footer_top + 12, cx + 418, footer_top + FOOTER_H - 12),
                           radius=34, fill=GOLD)
    # The ask is physical, not verbal: point at the screen. It's an action a kid
    # can do instantly while watching, so it reads as "play along" rather than a
    # chore — and it keeps hands/eyes on the video instead of in the comments.
    footer = "DID YOU GET IT?" if (reveal and factual) else ("DID YOU PICK IT?" if reveal else "POINT AT YOUR PICK!")
    _text_c(draw, cx, footer_top + 28, footer, _font("Anton-Regular.ttf", 60), NAVY, max_w=800)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


if __name__ == "__main__":
    import content
    it = content.daily_item("wyr", "2026-07-16")
    render(it, "output/frame_vote.png", countdown=3)
    render(it, "output/frame_reveal.png", reveal=True)
    print("rendered vote+reveal for:", it.a, "vs", it.b, f"({it.a_pct}/{it.b_pct})")
