"""Content for the kids fun-Shorts channel — all original, so it can monetize.

Five formats, all built around the same hook: show two things, count down, reveal
a percentage split (the % is made up on purpose — it's for fun and engagement).
`daily_item(format, date)` gives a stable-per-day pick so each day is fresh but a
day's video doesn't change between renders.
"""
from __future__ import annotations
import hashlib
import re
import json
import os
import random
from dataclasses import dataclass


@dataclass
class Item:
    prompt: str        # the line read aloud, e.g. "Would you rather..."
    a: str             # option A short text
    b: str             # option B short text
    a_emoji: str = ""
    b_emoji: str = ""
    # A drawable description of each option, for art.py. Claude writes these
    # alongside the question; the built-in pool falls back to art.ART_HINTS.
    a_art: str = ""
    b_art: str = ""
    a_pct: int = 0     # filled at pick time (made up)
    b_pct: int = 0
    fmt: str = "wyr"
    correct: int | None = None  # 0=a, 1=b for factual formats; None = opinion (no wrong answer)


# --- Topics --------------------------------------------------------------------
# Each video is about ONE thing: all food, or all superpowers, or all animals.
# A video of three unrelated questions has no identity — you can't title it, and
# it feels like leftovers. A themed one is "the food episode", the rounds build on
# each other, and the next day is visibly a different video.
# (label shown on the card, brief handed to Claude when it writes new questions)
TOPICS = {
    "food": ("FOOD EDITION",
             "food and eating: giving up a favourite food forever, endless supplies "
             "of one snack, weird food swaps, dream desserts"),
    "powers": ("SUPERPOWER EDITION",
               "superpowers and abilities: flying, invisibility, super speed, "
               "reading minds, freezing time, controlling elements"),
    "animals": ("ANIMAL EDITION",
                "animals and impossible pets: talking animals, dragons, dinosaurs, "
                "tiny or giant creatures, being an animal for a day"),
    "gaming": ("GAMING EDITION",
               "video games and gaming life: living inside a game, unlimited in-game "
               "money, being a pro gamer, game worlds becoming real"),
    "magic": ("MAGIC EDITION",
              "magic and fantasy: wands, spells, wizards, portals, magical objects, "
              "enchanted places, mythical creatures"),
    "space": ("SPACE EDITION",
              "space and adventure: rockets, living on other planets, aliens, "
              "exploring the ocean floor, secret bases"),
    "money": ("RICH EDITION",
              "money and luxury: piles of cash, owning anything you want, mansions, "
              "private islands, buying whole shops"),
    "school": ("SCHOOL EDITION",
               "school life: homework, tests, teachers, holidays, lunch, getting out "
               "of class, school but magical"),
}
_TOPIC_KEYS = sorted(TOPICS)
# Same idea as the palette rotation: STEP through the list rather than hashing, so
# two videos in a row can't land on the same topic. 8 topics, step 3 (coprime).
_TOPIC_FMT_OFFSET = {"wyr": 0, "this_or_that": 1, "rank": 2, "higher_lower": 3, "trivia": 4}


def topic_for(date: str, fmt: str = "") -> str:
    import datetime as _dt
    try:
        day = _dt.date.fromisoformat(str(date)[:10]).toordinal()
    except ValueError:
        day = sum(ord(c) for c in str(date))
    return _TOPIC_KEYS[(day * 3 + _TOPIC_FMT_OFFSET.get(fmt, 0)) % len(_TOPIC_KEYS)]


def topic_label(topic: str) -> str:
    return TOPICS.get(topic, ("", ""))[0]


# --- Format pools (kid-fun, broad appeal) --------------------------------------

WYR = [
    ("have $1,000,000", "have a real pet dragon", "💰", "🐉"),
    ("be invisible", "be able to fly", "👻", "🦅"),
    ("eat pizza forever", "eat ice cream forever", "🍕", "🍦"),
    ("have unlimited Robux", "have unlimited V-Bucks", "💎", "🎮"),
    ("live in Minecraft", "live in Roblox", "⛏️", "🎮"),
    ("fight 100 duck-sized horses", "fight 1 horse-sized duck", "🐴", "🦆"),
    ("never do homework again", "never be sick again", "📚", "🤒"),
    ("have a jetpack", "have a teleporter", "🚀", "🌀"),
    ("be the fastest kid alive", "be the strongest kid alive", "⚡", "💪"),
    ("have a talking dog", "have a talking cat", "🐶", "🐱"),
    ("control fire", "control water", "🔥", "💧"),
    ("have every video game free", "have every movie free", "🎮", "🎬"),
    ("be a famous YouTuber", "be a pro gamer", "📹", "🏆"),
    ("have a pet T-Rex", "have a pet giant spider", "🦖", "🕷️"),
    ("get $100 every day", "get a new phone every month", "💵", "📱"),
    ("shrink to ant size", "grow to giant size", "🐜", "🦍"),
    ("only eat candy", "only eat chips", "🍬", "🍟"),
    ("breathe underwater", "walk through walls", "🌊", "🧱"),
    ("have super speed", "read minds", "💨", "🧠"),
    ("own a private island", "own a private jet", "🏝️", "✈️"),
    ("have a lightsaber", "have a magic wand", "⚔️", "🪄"),
    ("be a superhero", "be a wizard", "🦸", "🧙"),
    ("have night vision", "have x-ray vision", "🌙", "🦴"),
    ("live on the moon", "live underwater", "🌕", "🐠"),
    ("have a robot butler", "have a flying car", "🤖", "🚗"),
    ("turn invisible", "turn into any animal", "🫥", "🐯"),
    ("have unlimited pizza", "have unlimited tacos", "🍕", "🌮"),
    ("be best at soccer", "be best at basketball", "⚽", "🏀"),
    ("have a pet penguin", "have a pet monkey", "🐧", "🐵"),
    ("get a puppy", "get a kitten", "🐕", "🐈"),
    ("have a treehouse", "have a secret underground base", "🌳", "🕳️"),
    ("have wings", "have a tail", "🪽", "🦎"),
    ("time travel to the past", "time travel to the future", "⏪", "⏩"),
    ("have a chocolate river", "have a candy mountain", "🍫", "🍭"),
    ("be super lucky", "be super smart", "🍀", "🧠"),
    ("have a pet unicorn", "have a pet phoenix", "🦄", "🔥"),
    ("never have to sleep", "never have to eat", "😴", "🍽️"),
    ("have a magic carpet", "have a hoverboard", "🧞", "🛹"),
    ("swim like a fish", "run like a cheetah", "🐟", "🐆"),
    ("have a giant water slide", "have a giant trampoline", "🛝", "🤸"),
    ("own a candy store", "own a toy store", "🍬", "🧸"),
    ("be able to teleport", "be able to freeze time", "🌀", "⏱️"),
    ("have a dinosaur as a pet", "ride a dragon to school", "🦕", "🐉"),
    ("have a pool full of jelly", "a pool full of slime", "🟢", "🫧"),
    ("be a famous singer", "be a famous actor", "🎤", "🎬"),
    ("have super strength", "have super hearing", "💪", "👂"),
    ("live in a candy house", "live in a giant treehouse", "🏠", "🌲"),
    ("have a magic backpack", "have magic shoes", "🎒", "👟"),
    ("be able to talk to animals", "speak every language", "🐾", "🗣️"),
    ("have a pet shark", "have a pet whale", "🦈", "🐋"),
    ("get every LEGO set", "get every Nerf gun", "🧱", "🔫"),
    ("have a jetpack to school", "a slide from your room", "🚀", "🛝"),
    ("be in your favorite movie", "be in your favorite game", "🎬", "🕹️"),
    ("have endless ice cream", "endless donuts", "🍦", "🍩"),
    ("control the weather", "control gravity", "🌦️", "🪐"),
    ("have a clone of yourself", "have a robot twin", "👥", "🤖"),
    ("be able to fly a plane", "drive a race car", "✈️", "🏎️"),
    ("have glow-in-the-dark skin", "color-changing hair", "✨", "🌈"),
    ("find $500 on the ground", "win a giant teddy bear", "💵", "🧸"),
    # --- pure daydream fuel -----------------------------------------------
    ("ride a dragon to school", "fly to school with wings", "🐉", "🪽"),
    ("live in a giant candy castle", "live in a floating cloud house", "🍭", "☁️"),
    ("have a magic door to anywhere", "have a rocket in your backyard", "🚪", "🚀"),
    ("have a dragon best friend", "have a unicorn best friend", "🐉", "🦄"),
    ("be a wizard with a wand", "be a knight with a sword", "🧙", "🗡️"),
    ("own a real spaceship", "own a real submarine", "🚀", "🤿"),
    ("have a pet baby dinosaur", "have a pet baby phoenix", "🦕", "🔥"),
    ("swim in a chocolate river", "fly through a candy sky", "🍫", "🍭"),
    ("have an invisible fort", "have a flying treehouse", "🏕️", "🌳"),
    ("command an army of robots", "command an army of dinosaurs", "🤖", "🦖"),
    ("live one day as a superhero", "live one day as a dragon", "🦸", "🐉"),
    ("have a room that becomes any world", "have a pet that becomes any animal", "🌍", "🐾"),
    ("find a real treasure chest", "find a real magic lamp", "💰", "🪔"),
    ("have shoes that let you run on water", "have gloves that let you climb walls", "👟", "🧤"),
    ("turn your homework into gold", "turn your bed into a spaceship", "📄", "🛏️"),
    # --- money (this topic was too thin to fill a 3-round video) -----------
    ("have a money tree in the garden", "have a vault full of gold coins", "🌳", "🪙"),
    ("be a billionaire kid", "own the biggest mansion ever", "💰", "🏰"),
    ("get paid to play video games", "get paid to eat snacks", "🎮", "🍿"),
    ("win the lottery every year", "find a pirate chest of gold", "🎟️", "💰"),
    ("buy any toy you want forever", "buy any game you want forever", "🧸", "🕹️"),
]

# Snap picks — kept IMAGINARY on purpose. "Summer vs Winter" and "Chocolate vs
# Vanilla" are things a kid already has an answer to; there's no daydream in it.
# Every pair here is a wish, so choosing means picturing yourself with it.
THIS_OR_THAT = [
    ("Dragon", "Unicorn", "🐉", "🦄"),
    ("Wizard", "Superhero", "🧙", "🦸"),
    ("Flying", "Invisibility", "🦅", "👻"),
    ("Magic wand", "Magic sword", "🪄", "⚔️"),
    ("Mermaid", "Fairy", "🧜", "🧚"),
    ("Robot friend", "Alien friend", "🤖", "👽"),
    ("Time machine", "Teleporter", "⏳", "🌀"),
    ("Candy world", "Toy world", "🍭", "🧸"),
    ("Magic castle", "Rocket ship", "🏰", "🚀"),
    ("Talking dog", "Talking cat", "🐶", "🐱"),
    ("Pet dinosaur", "Pet dragon", "🦕", "🐉"),
    ("Ice powers", "Fire powers", "❄️", "🔥"),
    ("Turn giant", "Turn tiny", "🦍", "🐜"),
    ("Treasure map", "Magic key", "🗺️", "🗝️"),
    ("Super speed", "Super strength", "⚡", "💪"),
    ("Pirate ship", "Space station", "🏴‍☠️", "🛰️"),
    ("Phoenix", "Griffin", "🔥", "🦅"),
    ("Invisible cloak", "Flying carpet", "🧥", "🧞"),
    # a couple of real-world snap picks so it isn't ALL fantasy
    ("Pizza", "Burgers", "🍕", "🍔"),
    ("Marvel", "DC", "🦸", "🦇"),
]

# (question, correct, wrong). These are stated to children as FACT, so every one
# must be settled and checkable — no records, no "currently", no trick questions.
TRIVIA = [
    # space
    ("Which planet is the biggest?", "Jupiter", "Mars"),
    ("Which planet is closest to the Sun?", "Mercury", "Venus"),
    ("Which planet is known as the Red Planet?", "Mars", "Jupiter"),
    ("What do we call a star that explodes?", "Supernova", "Black hole"),
    # animals
    ("How many legs does a spider have?", "8", "6"),
    ("What is the fastest land animal?", "Cheetah", "Lion"),
    ("How many hearts does an octopus have?", "3", "1"),
    ("What is the tallest animal?", "Giraffe", "Elephant"),
    ("Which animal is the largest on Earth?", "Blue whale", "Elephant"),
    ("What is a baby kangaroo called?", "Joey", "Cub"),
    ("Which bird cannot fly?", "Penguin", "Eagle"),
    ("How many legs does an insect have?", "6", "8"),
    # earth / nature
    ("How many continents are there?", "7", "5"),
    ("What is the biggest ocean?", "Pacific", "Atlantic"),
    ("What is the largest desert on Earth?", "Antarctica", "Sahara"),
    ("What gas do plants breathe in?", "Carbon dioxide", "Oxygen"),
    ("How many days are in a leap year?", "366", "365"),
    # colours / basics
    ("What color do blue and yellow make?", "Green", "Purple"),
    ("What color do red and blue make?", "Purple", "Orange"),
    ("How many sides does a hexagon have?", "6", "8"),
    ("How many minutes are in an hour?", "60", "100"),
    ("What is H2O better known as?", "Water", "Salt"),
]

# FIRST option is always the bigger (correct) one; the side is shuffled at build
# time. Every pair here must be UNAMBIGUOUSLY true — a kid gets told they were
# wrong, so "arguably bigger" isn't good enough.
HIGHER_LOWER = [
    # animals
    ("A blue whale", "A school bus", "🐋", "🚌"),
    ("A blue whale", "A T-Rex", "🐋", "🦖"),
    ("A T-Rex", "An elephant", "🦖", "🐘"),
    ("An elephant", "A horse", "🐘", "🐴"),
    ("A giraffe", "A polar bear", "🦒", "🐻‍❄️"),
    ("An ostrich", "A penguin", "🦤", "🐧"),
    ("A great white shark", "A dolphin", "🦈", "🐬"),
    # space
    ("The Sun", "The Earth", "☀️", "🌍"),
    ("Jupiter", "The Earth", "🪐", "🌍"),
    ("The Earth", "The Moon", "🌍", "🌕"),
    ("The Sun", "Jupiter", "☀️", "🪐"),
    # places / things
    ("Mount Everest", "The Eiffel Tower", "🏔️", "🗼"),
    ("The Pacific Ocean", "The Atlantic Ocean", "🌊", "🌎"),
    ("Russia", "Australia", "🇷🇺", "🇦🇺"),
    ("A football pitch", "A tennis court", "⚽", "🎾"),
    ("A jumbo jet", "A school bus", "✈️", "🚌"),
    ("A skyscraper", "A house", "🏢", "🏠"),
]

RANK = [  # a fun "which is better" pair, same reveal mechanic
    # animals
    ("Sharks", "Dinosaurs", "🦈", "🦖"),
    ("A lion", "A gorilla", "🦁", "🦍"),
    ("A T-Rex", "A giant squid", "🦖", "🦑"),
    ("A cheetah", "An eagle", "🐆", "🦅"),
    ("A grizzly bear", "A crocodile", "🐻", "🐊"),
    ("An elephant", "A rhino", "🐘", "🦏"),
    # magic / fantasy
    ("A dragon", "A phoenix", "🐉", "🔥"),
    ("A wizard", "A knight", "🧙", "🗡️"),
    ("A unicorn", "A griffin", "🦄", "🦅"),
    ("A giant", "A dragon", "🦍", "🐉"),
    ("A ninja", "A pirate", "🥷", "🏴‍☠️"),
    ("A werewolf", "A vampire", "🐺", "🧛"),
    # powers
    ("Super speed", "Super strength", "⚡", "💪"),
    ("Ice powers", "Fire powers", "❄️", "🔥"),
    ("Invisibility", "Flying", "👻", "🦅"),
    ("Mind reading", "Time freezing", "🧠", "⏱️"),
    # gaming / heroes
    ("Fortnite", "Minecraft", "🎮", "🟫"),
    ("Superman", "Batman", "🦸", "🦇"),
    ("Spider-Man", "Iron Man", "🕷️", "🤖"),
    ("A robot army", "A dinosaur army", "🤖", "🦖"),
    # space
    ("A rocket", "A spaceship", "🚀", "🛸"),
    ("An alien", "A robot", "👽", "🤖"),
]

# label, spoken prompt, pool, mode ("opinion" = made-up % split, no wrong answer;
# "factual" = one answer is correct and gets marked on the reveal).
FORMATS = {
    "wyr": ("WOULD YOU RATHER", "Would you rather", WYR, "opinion"),
    "this_or_that": ("THIS OR THAT", "Which do you pick", THIS_OR_THAT, "opinion"),
    "trivia": ("GUESS THE ANSWER", "Can you guess", TRIVIA, "factual"),
    "higher_lower": ("WHICH IS BIGGER", "Which one is bigger", HIGHER_LOWER, "factual"),
    "rank": ("WHO WOULD WIN", "Who would win", RANK, "opinion"),
}

# One format per weekday cycle, so the channel rotates through all five.
FORMAT_ROTATION = ["wyr", "this_or_that", "wyr", "higher_lower", "wyr", "rank", "trivia"]


# Which topic a built-in question belongs to. Only the FALLBACK pool needs this —
# questions Claude writes are already on-topic by construction. Checked in priority
# order because options overlap ("pet dragon" is animals AND magic; "unlimited
# Robux" is gaming AND money), and the first match wins.
_TOPIC_WORDS = {
    "school": ("homework", "school", "teacher", "test", "class"),
    "gaming": ("minecraft", "roblox", "fortnite", "robux", "v-buck", "video game",
               "pro gamer", "playstation", "xbox", "lego", "nerf", "favorite game"),
    "food": ("pizza", "ice cream", "candy", "chips", "taco", "donut", "chocolate",
             "vanilla", "burger", "eat ", "food", "jelly", "sweet", "cake"),
    "animals": ("dog", "cat", "dragon", "dinosaur", "t-rex", "spider", "penguin",
                "monkey", "shark", "whale", "unicorn", "phoenix", "animal", "puppy",
                "kitten", "horse", "duck", "cheetah", " pet", "tail", "wings"),
    "magic": ("magic", "wizard", "wand", "lightsaber", "portal", "genie", "lamp",
              "carpet", "spell", "invisible cloak", "treasure", "knight"),
    "space": ("moon", "space", "rocket", "spaceship", "alien", "planet", "submarine",
              "underwater", "island", "star"),
    "money": ("$", "money", "rich", "million", "dollar", "store", "jet", "gold",
              "mansion", "cash"),
    "powers": ("invisible", "fly", "super", "control", "read mind", "teleport",
               "freeze time", "x-ray", "night vision", "speed", "strength", "shrink",
               "giant", "breathe", "through walls", "gravity", "weather", "clone",
               "power", "time travel", "hero"),
}
_TOPIC_PRIORITY = ["school", "gaming", "food", "animals", "magic", "space", "money", "powers"]


def _has_word(text: str, word: str) -> bool:
    """Substring match with word boundaries.

    Plain `in` misfires badly here: "fastest" contains "test", so "be the fastest
    kid alive" was filed under SCHOOL.
    """
    w = word.strip()
    if not w:
        return False
    if not w[0].isalpha():          # "$" and friends have no word boundary
        return w in text
    return re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text) is not None


def row_topic(row) -> str:
    """Best-guess topic for a built-in row, or 'misc'."""
    t = f"{row[0]} {row[1]}".lower()
    for topic in _TOPIC_PRIORITY:
        if any(_has_word(t, w) for w in _TOPIC_WORDS[topic]):
            return topic
    return "misc"


def _rng(*parts) -> random.Random:
    seed = int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def _split(rng: random.Random) -> tuple[int, int]:
    """A believable made-up split — always LOPSIDED, never close to a tie.

    A 52/48 reveal is a dud: you sit through a countdown to hear "it's basically
    even". A lopsided number is the whole payoff — it either confirms you or tells
    you you're in the weird minority, and that's what makes people argue in the
    comments. So the floor is ~63/37, not 52/48.

    Capped at ~79/21, though: at 91/9 the question stops being a question. The
    minority has to stay big enough to feel like a real camp that fights back —
    that argument IS the comment section.
    """
    a = rng.choice([63, 66, 69, 72, 76, 79])
    return (a, 100 - a) if rng.random() < 0.5 else (100 - a, a)


def _build(fmt: str, row: tuple, rng: random.Random) -> Item:
    label, prompt, pool, mode = FORMATS[fmt]
    if mode == "factual":
        # Padded because pool rows are short (no art) while generated rows carry
        # emoji + art descriptions. The CORRECT option is always first in the row.
        r = tuple(row) + ("",) * 4
        if fmt == "trivia":                       # (question, correct, wrong, ...)
            prompt, correct_text, wrong_text = r[0], r[1], r[2]
            ae, be, a_art_c, b_art_w = r[3], r[4], r[5], r[6]
        else:                                     # (bigger, smaller, ...) — first is correct
            correct_text, wrong_text = r[0], r[1]
            ae, be, a_art_c, b_art_w = r[2], r[3], r[4], r[5]
        # Shuffle which side the correct answer sits on.
        if rng.random() < 0.5:
            a, b, a_e, b_e, a_art, b_art, correct = (correct_text, wrong_text, ae, be,
                                                     a_art_c, b_art_w, 0)
        else:
            a, b, a_e, b_e, a_art, b_art, correct = (wrong_text, correct_text, be, ae,
                                                     b_art_w, a_art_c, 1)
        # "% who got it right" — deliberately skewed LOW. "Only 23% got this"
        # makes a viewer who got it feel smart (and want to say so); "72% got it"
        # is a shrug. The hard ones are the ones people brag about in comments.
        win = rng.choice([17, 23, 29, 34, 41, 48, 56])
        a_pct, b_pct = (win, 100 - win) if correct == 0 else (100 - win, win)
        return Item(prompt=prompt, a=a, b=b, a_emoji=a_e, b_emoji=b_e,
                    a_art=a_art, b_art=b_art, a_pct=a_pct, b_pct=b_pct,
                    fmt=fmt, correct=correct)

    # Generated rows carry two extra fields (the art descriptions); pool rows don't.
    a, b, ae, be, a_art, b_art = (tuple(row) + ("", "", "", ""))[:6]
    a_pct, b_pct = _split(rng)
    return Item(prompt=prompt, a=a, b=b, a_emoji=ae, b_emoji=be, a_art=a_art, b_art=b_art,
                a_pct=a_pct, b_pct=b_pct, fmt=fmt, correct=None)


def daily_item(fmt: str | None = None, date: str = "today") -> Item:
    if fmt is None:
        fmt = FORMAT_ROTATION[_rng("fmt", date).randrange(len(FORMAT_ROTATION))]
    pool = FORMATS[fmt][2]
    row = pool[_rng(fmt, date).randrange(len(pool))]
    return _build(fmt, row, _rng(fmt, date))


# --- No-repeat picking: remember what's been used so every post is different ----

def _key(row: tuple) -> str:
    return f"{row[0]}|{row[1]}"


def _used_path(fmt: str) -> str:
    return os.path.join(os.path.dirname(__file__), "output", f"used_{fmt}.json")


def _load_used(fmt: str) -> set[str]:
    try:
        with open(_used_path(fmt)) as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def _save_used(fmt: str, keys: set[str]) -> None:
    os.makedirs(os.path.dirname(_used_path(fmt)), exist_ok=True)
    with open(_used_path(fmt), "w") as f:
        json.dump(sorted(keys), f)


def several(fmt: str, date: str | None = None, n: int = 3, avoid_repeats: bool = True,
            topic: str | None = None) -> list[Item]:
    """n distinct items of one format, all on ONE topic.

    Prefers freshly AI-generated questions (so every post is brand-new); falls back
    to the curated pool so the bot always works. Never repeats a question until
    everything's been used.

    The topic is a REQUEST, not a guarantee: Claude writes to it, but the fallback
    pool only has a handful per topic, so if it can't fill the video it tops up
    from the rest rather than shipping a two-round Short. Callers check
    `is_themed()` before printing "FOOD EDITION" over a mixed bag.
    """
    import generate
    pool = FORMATS[fmt][2]
    if topic:
        on_topic = [r for r in pool if row_topic(r) == topic]
        if len(on_topic) >= n:
            pool = on_topic
    n = min(n, len(pool))
    used = _load_used(fmt) if avoid_repeats else set()
    rng = random.Random()
    chosen: list[tuple] = []
    picked_keys: set[str] = set()

    # 1) brand-new questions from Claude, skipping anything already used
    for row in generate.generate(fmt, n, avoid=sorted(used), topic=topic):
        k = _key(row)
        if k not in used and k not in picked_keys:
            chosen.append(row)
            picked_keys.add(k)
            if len(chosen) >= n:
                break

    # 2) top up from the curated pool if generation was unavailable or short
    if len(chosen) < n:
        avail = [r for r in pool if _key(r) not in used and _key(r) not in picked_keys]
        if len(avail) < n - len(chosen):         # pool exhausted -> fresh cycle
            used = set(picked_keys)
            avail = [r for r in pool if _key(r) not in picked_keys]
        for row in rng.sample(avail, n - len(chosen)):
            chosen.append(row)
            picked_keys.add(_key(row))

    if avoid_repeats:
        _save_used(fmt, used | picked_keys)
    built = [_build(fmt, row, random.Random()) for row in chosen]

    # Escalate: put the most extreme reveal LAST. Viewers bail after a payoff, so
    # the biggest "no way" has to be the thing they're still waiting for at the
    # end — that's what buys rounds 2 and 3.
    built.sort(key=_extremeness)
    return built


def _extremeness(it: Item) -> float:
    """Sort key: bigger = saved for later.

    Opinion rounds escalate on how lopsided the split is. Factual rounds escalate
    on DIFFICULTY (fewest people got it right) — the gap can't be used there,
    because a 48%-correct question has a tiny gap yet is harder than a 56% one.
    """
    if it.correct is not None:
        return 100 - (it.a_pct if it.correct == 0 else it.b_pct)
    return abs(it.a_pct - it.b_pct)


def format_label(fmt: str) -> str:
    return FORMATS[fmt][0]


def is_themed(items: list[Item], topic: str | None) -> bool:
    """True only if EVERY round really is on the topic.

    Guards the on-screen label: the fallback pool can't always fill a topic, and
    stamping "FOOD EDITION" over a video that's two-thirds superpowers is worse
    than showing no label at all.
    """
    if not topic or not items:
        return False
    return all(row_topic((it.a, it.b)) == topic for it in items)


if __name__ == "__main__":
    for d in ["2026-07-15", "2026-07-16", "2026-07-17", "2026-07-18", "2026-07-19"]:
        it = daily_item(date=d)
        print(f"{d}  [{it.fmt}]  {it.prompt}: {it.a} ({it.a_pct}%) vs {it.b} ({it.b_pct}%)")
