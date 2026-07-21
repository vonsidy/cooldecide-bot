"""Generates brand-new questions with Claude, so the bot never runs out and every
post is original. Falls back to the curated pools in content.py when no API key
is set or a call fails, so the bot always works.

Set ANTHROPIC_API_KEY (env or a local .env) to enable generation.
"""
from __future__ import annotations
import json
import os
import re

MODEL = "claude-haiku-4-5-20251001"   # fast + cheap, plenty for short questions

_SAFE = ("Wholesome and safe for a young audience: no violence, weapons aimed at "
         "people, scary/horror, politics, or gross-out, and nothing beyond an "
         "INNOCENT crush (a nervous text, a school dance — never anything physical "
         "or adult). Keep it playful.")

# The pull of this format is the DAYDREAM, not the preference. "Summer or Winter"
# is something a kid already has an answer to, so there's nothing to picture and
# nothing to argue about. "Dragon or unicorn" makes them imagine owning one.
_IMAGINATIVE = (
    "\nMake them IMAGINATIVE and magical — wish-fulfilment a kid would daydream "
    "about: powers, creatures, magic, space, secret worlds, impossible pets, being "
    "a hero. Both options must be things they'd genuinely WANT, so picking HURTS. "
    "Every option must be something you could draw a fun picture of.\n"
    "BANNED — real-world preferences a kid already has an answer to, which leave "
    "nothing to imagine and nothing to argue about. These are failures, not "
    "examples: 'summer vs winter', 'chocolate vs vanilla', 'dogs vs cats', "
    "'private island vs private jet', 'puppy vs kitten', 'best at soccer vs best "
    "at basketball', 'famous singer vs famous actor'. Merely OWNING an expensive "
    "thing is not imagination — a swimming pool full of gold coins is.\n"
    "Test each one: could a kid close their eyes and SEE themselves in it? If not, "
    "throw it away."
)

# WYR lives or dies on the AGONY of the choice, not the whimsy of the options.
# "Pet dragon vs pet dinosaur" is cute but easy; "never do homework again vs go on
# a date with your crush" starts an argument in the comments. Owner's brief: make
# picking hurt, and write for TEENAGERS.
#
# Teen used to be a slice ("skew a good slice slightly older") sitting inside a brief
# that said "kid" everywhere else — so the model averaged the two and landed young.
# 13-17 is now the default and little-kid framing is banned outright. The fallback
# pool already worked this way (content.several draws untopiced wyr from WYR_TEEN);
# this makes the AI agree with it instead of contradicting it.
_DILEMMA = (
    "\nMake every one GENUINELY HARD to choose — picking must HURT. Two shapes "
    "work:\n"
    "  * dream vs dream: two things they'd BOTH desperately want — 'never do "
    "homework again' vs 'go on a date with your crush'.\n"
    "  * loss vs loss: two things they'd HATE to give up — 'give up YouTube "
    "forever' vs 'give up Instagram forever'.\n"
    "STAY IN THE REAL WORLD TEENAGERS actually live in — that is what makes them "
    "argue. Write for 13-17 BY DEFAULT, not for little kids: the voter is in high "
    "school, has a phone, a group chat and an opinion about who's fake. AT LEAST 4 "
    "of every 5 must be real-life stakes they care about TODAY: social media "
    "(Instagram vs TikTok vs Snapchat, losing your streak, going viral, follower "
    "count, getting exposed in the comments), phones/screen time, school (tests, "
    "grades, a strict teacher, group projects), friendships, popularity and social "
    "standing (being talked about, getting left out of plans, the group chat), "
    "gaming (rank, skins, your main account), money and a first job, independence "
    "(driving, staying out, your own room), and an innocent crush (texting first, "
    "sitting next to them, being left on read). Keep it totally clean. At most 1 in "
    "5 may be imaginative (a power or a wish) — and only if the choice still "
    "genuinely HURTS. NEVER whimsical creatures/pets (dragons, unicorns, talking "
    "animals, magic genies) and never little-kid framing (recess, the playground, "
    "your teacher's sticker chart, losing a tooth): a 15-year-old does not care "
    "about a dragon that tells 500-year-old stories, they care about their phone, "
    "their friends and their crush.\n"
    "The test: imagine 100 TEENAGERS voting — if it wouldn't split close to 50/50, "
    "it's too easy, throw it away. 'Summer vs winter', 'dogs vs cats', 'pizza vs "
    "burgers' are failures: everyone already has an answer.\n"
    "BOTH options must point the SAME WAY: two things they WANT (dream vs dream) or "
    "two things they'd HATE (loss vs loss) — NEVER one of each. 'Text your crush "
    "first' (a scary thing you have to DO) against 'never get left on read' (a gift "
    "you RECEIVE) is not a dilemma, it's a free choice: the gift wins and nobody "
    "hesitates for a second. If one side costs something and the other hands "
    "something over, the question answers itself and the video is dead. Pair a cost "
    "with a COST ('text your crush first' vs 'wait forever for them to text you') "
    "and a gift with a GIFT.\n"
    "BIGGEST failure to avoid — two nice-to-haves with NO downside, where a teen "
    "would be thrilled with EITHER and just shrug ('both are awesome, whatever'): "
    "'pet dragon vs pet unicorn', 'talking dog vs talking cat', 'fly vs be "
    "invisible', 'pet dragon vs pet phoenix'. Two cool things is NOT a dilemma. The "
    "AGONY of LOSING the one you don't pick is the entire point — if giving it up "
    "doesn't sting, the question is dead. Every option must be something you could "
    "draw."
)

_PROMPTS = {
    # opinion formats: two fun options, each with one fitting emoji
    "wyr": ("'would you rather' dilemmas TEENAGERS would genuinely argue about, where "
            "picking one means painfully giving up the other (social media and clout, "
            "the group chat, school, friendships and popularity, gaming, money and a "
            "first job, independence, an innocent crush)",
            '{"a":"Wake up with 1M followers","a_emoji":"\\ud83d\\udcc8","a_art":"a phone screen showing a million followers",'
            '"b":"Your crush texts you first every day","b_emoji":"\\ud83d\\udcac","b_art":"a phone screen showing a text from a crush"}'),
    "this_or_that": ("quick 'this or that' preferences (one word or short each)",
                     '{"a":"Pizza","a_emoji":"\\ud83c\\udf55","a_art":"a slice of pizza",'
                     '"b":"Burgers","b_emoji":"\\ud83c\\udf54","b_art":"a cheeseburger"}'),
    # "matchups" alone wasn't enough — with a money theme it produced "Who would
    # win: owning every video game vs owning every pizza restaurant", which is a
    # would-you-rather wearing a battle's label. Both sides must be able to FIGHT.
    "rank": ("'who would win' FIGHTS kids are obsessed with, between FAMOUS, instantly "
             "recognisable characters a kid knows today: superheroes and villains "
             "(Spider-Man, Batman, Hulk, Venom, Iron Man), video-game and cartoon "
             "characters (Mario, Sonic, Pikachu, Goku, Minecraft Steve), or famous "
             "giant monsters (Godzilla, King Kong, a dragon, a T-rex). Mix BOTH kinds "
             "of matchup: (1) classic 1-vs-1 dream fights (Spider-Man vs Batman, Mario "
             "vs Sonic, Goku vs Superman); and (2) 'numbers vs power' battles pitting "
             "many weaker famous characters against a few strong ones (100 Minions vs "
             "1 Hulk, 1,000 Stormtroopers vs 5 Jedi, 20 Goombas vs 3 Marios) — for "
             "these keep the count in the option text and make the art show a CROWD vs "
             "a SINGLE or FEW (image models can't draw an exact number). Both sides "
             "must be FIGHTERS that can square up — never possessions, places, foods, "
             "or wishes. Cross-universe matchups are great; use real, well-known "
             "characters, never made-up ones",
             '{"a":"100 Minions","a_emoji":"👾","a_art":"a big crowd of little yellow cartoon henchmen",'
             '"b":"1 Hulk","b_emoji":"💚","b_art":"one huge green muscular superhero"}'),
    # Factual formats — a different JSON shape, because one answer is RIGHT.
    "trivia": ("fun general-knowledge quiz questions kids would enjoy guessing",
               '{"question":"Which planet is the biggest?","correct":"Jupiter",'
               '"wrong":"Mars","correct_emoji":"\\ud83e\\ude90","wrong_emoji":"\\ud83d\\udd34",'
               '"correct_art":"the planet Jupiter","wrong_art":"the planet Mars"}'),
    "higher_lower": ("'which is bigger' comparisons between two well-known things",
                     '{"bigger":"A blue whale","smaller":"A school bus",'
                     '"bigger_emoji":"\\ud83d\\udc0b","smaller_emoji":"\\ud83d\\ude8c",'
                     '"bigger_art":"a blue whale","smaller_art":"a yellow school bus"}'),
}

# Formats where one answer is genuinely RIGHT. These are the only ones where the
# bot can state something false, so the brief is much stricter than for opinions.
FACTUAL = {"trivia", "higher_lower"}

_FACT_RULE = (
    "\nCRITICAL: this is a QUIZ, so the answer must be genuinely, checkably TRUE — "
    "a kid will be told they were wrong, and a parent will see it. Only use "
    "well-established facts that don't change over time (no records, no 'current' "
    "anything, no populations, no prices). No trick questions and no ambiguity: the "
    "wrong option must be CLEARLY wrong, not arguable. Prefer facts a curious "
    "10-year-old could look up in seconds. If you are not certain it is true, pick a "
    "different question."
)

# Each option also needs a drawable description. An image model can't interpret an
# abstract option: prompted with "never do homework again" it draws a kid DOING
# homework, and "be invisible" draws a plainly visible girl. Claude writes the
# option and the picture for it in the SAME call, so this costs nothing extra.
_ART_RULE = (
    "\nEach option also needs \"a_art\"/\"b_art\": a short, CONCRETE description of a "
    "single picture that represents it, for a cartoon illustrator. It must be "
    "physically drawable — never an abstract phrase. Bad: \"never do homework again\". "
    "Good: \"a happy kid throwing homework papers into the air\". If the option is "
    "already a thing you can draw (a dragon, pizza), just describe that thing."
)

# The opening decides everything on Shorts: if the first card isn't instantly
# recognisable, the viewer swipes before the hook lands. So the FIRST item must be
# the most universally-known one, not a deep cut.
_HOOK_RULE = (
    "\nORDER MATTERS — the FIRST item decides if a scroller stays in the first 2 "
    "seconds. Do NOT lead with the most 'famous' one: recognising a topic is not the "
    "same as having to answer it, and recognisability alone does not stop a scroll. "
    "Lead with the single most DIVISIVE + RELATABLE choice — an everyday teen/kid "
    "dilemma they have an INSTANT hot take on and suspect their pick is the minority "
    "(crush, texting first / left on read, streaks, followers, going viral, phones, "
    "group chat, friend drama, popularity, being embarrassed). It must be a REAL "
    "near-50/50 split, totally clean, and never mean — no rage-bait, no fake claim. "
    "Save the tamer or more niche ones for later. (For 'who would win', divisive "
    "means a genuinely EVEN, argue-in-the-comments matchup — not a curbstomp.)"
)


def available() -> bool:
    return bool(_api_key())


def _api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env):
        for line in open(env):
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _rows_from_json(text: str, fmt: str) -> list[tuple]:
    """Parse Claude's JSON into the row shape content.py expects for this format.

    The three shapes differ because the formats do: opinion rounds have two equal
    options, trivia has a question plus a right/wrong answer, and which-is-bigger
    has an ordered pair. Row order matters — content._build reads them positionally
    and puts the CORRECT one first for factual formats.
    """
    match = re.search(r"\[.*\]", text, re.DOTALL)
    data = json.loads(match.group(0) if match else text)
    rows = []
    for d in data:
        if fmt == "trivia":
            q, c, w = d.get("question"), d.get("correct"), d.get("wrong")
            if q and c and w:
                rows.append((str(q), str(c), str(w),
                             str(d.get("correct_emoji", "")), str(d.get("wrong_emoji", "")),
                             str(d.get("correct_art", "")), str(d.get("wrong_art", ""))))
        elif fmt == "higher_lower":
            b_, s_ = d.get("bigger"), d.get("smaller")
            if b_ and s_:
                rows.append((str(b_), str(s_),
                             str(d.get("bigger_emoji", "")), str(d.get("smaller_emoji", "")),
                             str(d.get("bigger_art", "")), str(d.get("smaller_art", ""))))
        else:
            a, b = d.get("a"), d.get("b")
            if a and b:
                rows.append((str(a), str(b), str(d.get("a_emoji", "")), str(d.get("b_emoji", "")),
                             str(d.get("a_art", "")), str(d.get("b_art", ""))))
    return rows


# A stricter brief was not enough. Graded over 24 generated matchups, 3 still came
# back as would-you-rathers wearing a battle's label ("You as a mighty eagle vs You
# as a giant octopus"). A prompt can only ask; this checks. Anything that can't
# fight is dropped before it reaches a card.
_FIGHT_JUDGE = (
    "These are meant to be WHO WOULD WIN matchups on a kids' channel — a FIGHT "
    "between two things that could genuinely battle each other.\n\n"
    "For each numbered pair, decide: could a kid picture the two SQUARING UP against "
    "each other? Answer false if either side is a possession, a place, a food, a "
    "wish, a transformation of the viewer ('you as a shark'), or if the two are "
    "separate scenarios that never meet ('kid trapped in a game vs character trapped "
    "in school'). Both sides must be able to act, hit, and lose. Be strict — when "
    "unsure, answer false.\n\n"
    "Return ONLY a JSON array of booleans, one per pair, in order. Nothing else."
)


def _fight_check(rows: list[tuple], key: str) -> list[tuple]:
    """Keep only the matchups that are actually a fight.

    Fails CLOSED: any error returns nothing, so the caller falls back to the
    hand-vetted pool. Shipping an unchecked matchup is the failure this exists to
    prevent, so "check unavailable" must never mean "send it anyway".
    """
    if not rows:
        return []
    try:
        import anthropic
        listing = "\n".join(f"{i + 1}. {r[0]} vs {r[1]}" for i, r in enumerate(rows))
        # Bounded so a slow Anthropic can't hang the CI job; on error this fails closed
        # to the hand-vetted pool (see the caller), which is the safe outcome.
        msg = anthropic.Anthropic(api_key=key, max_retries=0, timeout=30.0).messages.create(
            model=MODEL, max_tokens=300, temperature=0,
            messages=[{"role": "user", "content": f"{_FIGHT_JUDGE}\n\n{listing}"}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        match = re.search(r"\[.*\]", text, re.DOTALL)
        flags = json.loads(match.group(0)) if match else []
        if len(flags) != len(rows):
            return []
        return [r for r, ok in zip(rows, flags) if ok is True]
    except Exception:
        return []


def generate(fmt: str, n: int, avoid: list[str] | None = None,
             topic: str | None = None) -> list[tuple]:
    """Returns rows in the same shape as content.py's pools, or [] on any failure.

    `topic` makes the whole video about one thing (all food, all superpowers), so
    it has an identity instead of being three unrelated questions.
    """
    key = _api_key()
    if not key or fmt not in _PROMPTS:
        return []
    try:
        import anthropic
        import content
        # Bounded so a slow Anthropic can't hang the CI job; on error this returns []
        # and the caller falls back to the curated pool, so the bot still posts.
        client = anthropic.Anthropic(api_key=key, max_retries=1, timeout=60.0)
        kind, example = _PROMPTS[fmt]
        if topic and topic in content.TOPICS:
            kind = (f"{kind}. EVERY question must be about ONE theme — "
                    f"{content.TOPICS[topic][1]}")
        # `avoid` arrives OLDEST FIRST (content._load_used_list), so the tail really
        # is the most recent history — it used to be sorted alphabetically, making
        # this slice an arbitrary s-z window.
        # Naming both halves matters: repeating ONE option in a new pairing is the
        # recycling that slipped through, since dedup upstream only matches whole pairs.
        avoid_txt = ("\nThese exact questions have already been used. Do NOT repeat or "
                     "closely echo any of them, and do NOT reuse EITHER SIDE of one in "
                     "a new pairing — both options must be new:\n- "
                     + "\n- ".join((avoid or [])[-40:])) if avoid else ""
        prompt = (
            # "for a kids' channel" used to sit here, above every other instruction,
            # and quietly outranked the teen brief below it. The channel's audience
            # is teenagers; _SAFE still keeps the content clean.
            f"Write {n + 3} original {kind} for a teen YouTube Shorts channel. {_SAFE}\n"
            f"Each needs two short options (2-6 words) and one fitting emoji per option. "
            f"Use clear object emojis, never plain colored squares/circles. Be creative and varied."
            f"{_DILEMMA if fmt == 'wyr' else ''}"
            f"{_IMAGINATIVE if fmt == 'this_or_that' else ''}"
            f"{_FACT_RULE if fmt in FACTUAL else ''}"
            f"{_ART_RULE}"
            f"{_HOOK_RULE}"
            f"{avoid_txt}\n\n"
            f'Return ONLY a JSON array of objects like: {example}'
        )
        msg = client.messages.create(
            model=MODEL, max_tokens=1400,
            # Facts don't benefit from creativity — turn the temperature down so it
            # reaches for the well-known answer instead of an interesting one.
            temperature=0.4 if fmt in FACTUAL else 1.0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        rows = _rows_from_json(text, fmt)
        if fmt == "rank":
            rows = _fight_check(rows, key)
        return rows
    except Exception:
        return []


if __name__ == "__main__":
    print("generation available:", available())
    if available():
        for r in generate("wyr", 3):
            print("  ", r)
