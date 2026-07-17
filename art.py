"""Generates a cartoon sticker for ANY option, so every card has art.

Why generate instead of searching a photo library
-------------------------------------------------
Most options aren't photographable. "Never do homework again" has no photo, and
a stock search for it returns junk (a real search for "be in your favorite movie"
returned a beer advert). Generation covers everything AND gives one consistent
look, instead of a mishmash of stock photos in different styles.

The catch, and the fix
----------------------
An image model can't interpret an abstract option either — prompted with the raw
text "never do homework again" it drew a kid DOING homework, and "being invisible"
drew a plainly visible girl. So the option is translated into something concrete
and drawable FIRST ("a happy kid throwing homework papers into the air"), which
renders perfectly. That translation comes from:
  1. `hint` — Claude writes one per option when it writes the question (generate.py)
  2. ART_HINTS — hand-written for the built-in pool
  3. the raw option text — fine for concrete things ("a pet dragon" is great)

Images are cached on disk and committed, so the cloud never regenerates (it's
~10-45s per image) and never ships art nobody reviewed.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://image.pollinations.ai/prompt/"
CACHE = os.path.join(os.path.dirname(__file__), "assets", "art")
UA = {"User-Agent": "cooldecide-bot/0.1"}
TIMEOUT = 100
RETRIES = 4
BACKOFF = 6      # seconds; multiplied on 429 and by attempt number

# One house style for every card. Flat sticker art on white reads instantly at
# thumbnail size and cuts out cleanly against the coloured panels.
STYLE = ("cute simple flat cartoon sticker illustration of {}, bold clean outlines, "
         "vibrant colors, plain white background, centered, no text, for kids")

# Abstract options translated into something an image model can actually draw.
# Concrete options ("have a pet dragon") are left out — the raw text works.
ART_HINTS = {
    "be invisible": "a child turning see-through and transparent, fading outline",
    "turn invisible": "a child turning see-through and transparent, fading outline",
    "be able to fly": "a happy kid flying through the sky, arms stretched out",
    "never do homework again": "a happy kid throwing homework papers into the air",
    "never be sick again": "a strong healthy kid flexing, glowing with health",
    "be the fastest kid alive": "a kid running super fast with speed lines",
    "be the strongest kid alive": "a kid lifting a huge heavy dumbbell",
    "control fire": "a hand shooting a burst of flames",
    "control water": "a hand swirling a ribbon of water in the air",
    "have super speed": "a kid running so fast they blur, speed lines",
    "read minds": "a head with floating thought bubbles and question marks",
    "shrink to ant size": "a tiny kid standing next to a giant ant",
    "grow to giant size": "a giant kid towering over tiny houses",
    "breathe underwater": "a smiling kid breathing happily underwater with fish",
    "walk through walls": "a kid stepping straight through a brick wall",
    "have night vision": "glowing green eyes seeing in the dark",
    "have x-ray vision": "eyes with beams revealing a skeleton hand",
    "time travel to the past": "a kid stepping into a swirling portal toward a dinosaur",
    "time travel to the future": "a kid stepping into a glowing futuristic portal",
    "be super lucky": "a kid holding a four leaf clover surrounded by sparkles",
    "be super smart": "a kid with a glowing brain and a stack of books",
    "never have to sleep": "a wide awake happy kid at night under a moon",
    "never have to eat": "a kid cheerfully pushing away a plate of food",
    "swim like a fish": "a kid swimming fast underwater like a fish",
    "run like a cheetah": "a kid racing alongside a cheetah",
    "be able to teleport": "a kid vanishing into a swirling portal",
    "be able to freeze time": "a kid standing still while frozen clocks float around",
    "be able to talk to animals": "a kid happily chatting with a dog and a bird",
    "speak every language": "a kid surrounded by colorful speech bubbles",
    "turn into any animal": "a kid transforming into a tiger",
    "control the weather": "a kid holding a storm cloud in one hand and sunshine in the other",
    "control gravity": "a kid floating objects in the air around them",
    "have a clone of yourself": "two identical smiling kids standing side by side",
    "have a robot twin": "a kid standing beside a friendly robot copy of themselves",
    "have glow-in-the-dark skin": "a kid glowing brightly in the dark",
    "color-changing hair": "a kid with rainbow color-changing hair",
    "have unlimited robux": "a big pile of shiny blue gems",
    "have unlimited v-bucks": "a big pile of glowing gold coins",
    "get $100 every day": "a happy kid holding a fan of banknotes",
    "have $1,000,000": "a huge pile of money and gold coins",
    "find $500 on the ground": "a kid picking up money off the pavement",
    "be a famous youtuber": "a kid filming themselves with a camera and ring light",
    "be a pro gamer": "a kid with a headset winning at a gaming setup",
    "never sick": "a healthy glowing kid",
    "have a magic backpack": "a glowing magical backpack with sparkles",
    "have magic shoes": "a pair of glowing magical sneakers with sparkles",
    "own a candy store": "a kid behind the counter of a colorful candy shop",
    "own a toy store": "a kid inside a bright toy shop full of toys",
    "be in your favorite movie": "a kid stepping into a glowing cinema screen",
    "be in your favorite game": "a kid stepping into a glowing video game world",
    "have every video game free": "a kid holding a huge stack of game boxes",
    "have every movie free": "a kid surrounded by floating film reels and popcorn",

    # ---- FACTUAL formats (quiz / which-is-bigger) ----------------------------
    # On these cards the picture is part of the CLAIM, so a wrong one teaches a kid
    # something false. Prompted with the bare label "Jupiter" the model drew a
    # ringed planet — Saturn — on a card asking which is bigger. Every hint below
    # pins the identifying details rather than trusting the model to know.
    # space
    "jupiter": "the planet Jupiter, banded orange and cream clouds, one great red spot, NO rings",
    "the sun": "the sun as a glowing yellow-orange star with a bright fiery corona",
    "the earth": "planet Earth from space, blue oceans, green continents, white clouds",
    "the moon": "the grey cratered moon, plain and rocky, no rings",
    "mars": "the planet Mars, a dusty rust-red ball with dark patches, no rings",
    "mercury": "the planet Mercury, a small dull grey cratered ball, no rings",
    "venus": "the planet Venus, a pale creamy yellow-white cloudy ball, no rings",
    "supernova": "a star bursting outward, brilliant white core with shockwaves of light",
    "black hole": "a pure black circle in space ringed by a glowing orange halo of light",
    # animals — the species has to be unmistakable or the claim breaks
    "a blue whale": "an enormous blue-grey whale swimming, long grooved throat",
    "blue whale": "an enormous blue-grey whale swimming, long grooved throat",
    "a t-rex": "a green tyrannosaurus rex standing, big head, tiny arms",
    "an elephant": "a grey elephant with huge ears, long trunk and white tusks",
    "elephant": "a grey elephant with huge ears, long trunk and white tusks",
    "a horse": "a brown horse standing side on",
    "a giraffe": "a giraffe with a very long neck and brown patches",
    "giraffe": "a giraffe with a very long neck and brown patches",
    "a polar bear": "a white polar bear standing on snow",
    "an ostrich": "an ostrich, a tall bird with long bare pink legs, grey-black plumes, small head",
    "a penguin": "an emperor penguin standing, black back, white belly, orange neck patch",
    "penguin": "an emperor penguin standing, black back, white belly, orange neck patch",
    "a great white shark": "a great white shark, grey back, white belly, pointed snout",
    "a bottlenose dolphin": "a grey bottlenose dolphin leaping, short rounded beak",
    "cheetah": "a slender spotted cheetah running, black tear lines on its face",
    "lion": "a male lion with a full golden mane",
    "joey": "a baby kangaroo peeking out of its mother's pouch",
    "cub": "a small fluffy brown bear cub sitting",
    "eagle": "a bald eagle with a white head and brown body, wings spread",
    # places — a globe turned to the right ocean, not a generic wave
    "mount everest": "an immense snow-capped rocky mountain peak above the clouds",
    "the eiffel tower": "the Eiffel Tower, a tall brown iron lattice tower",
    "the pacific ocean": "a globe turned to show one enormous blue ocean filling the face",
    "pacific": "a globe turned to show one enormous blue ocean filling the face",
    "the atlantic ocean": "a globe showing a blue ocean with land on both its left and right",
    "atlantic": "a globe showing a blue ocean with land on both its left and right",
    "russia": "a flat map silhouette of one very wide country stretching left to right",
    "australia": "a flat map silhouette of Australia, an island continent",
    "a football pitch": "a green football pitch from above, white lines and goals",
    "a tennis court": "a tennis court from above, white lines and a net across the middle",
    "a jumbo jet": "a large white passenger jet airliner in flight",
    "a school bus": "a yellow school bus, side view",
    "a skyscraper": "one very tall glass office tower",
    "a house": "a small cosy house with a red pitched roof",
    "sahara": "endless rolling golden sand dunes under a blazing sun",
    "gobi": "a cold stony desert, bare gravel plains and dry scrub, no sand dunes",
    # science / colour — flat swatches, because the colour IS the answer
    "carbon dioxide": "a green leaf with small grey gas bubbles drifting into it",
    "nitrogen": "a drifting cloud of pale blue gas bubbles",
    "green": "a flat blob of bright green paint",
    "purple": "a flat blob of purple paint",
    "orange": "a flat blob of orange paint",
    "water": "a clear glass of water with one droplet splashing",
    "salt": "a small heap of white salt grains beside a salt shaker",

    # ---- WHO WOULD WIN archetypes -------------------------------------------
    # Named characters (Superman, Batman, Spider-Man, Iron Man) were replaced with
    # archetypes: the pipeline draws and monetises every option, and those costumes
    # are someone else's property. These describe the trope, not the character.
    "a super-fast hero": "a smiling hero dashing forward in a plain costume, speed lines trailing",
    "a super-strong hero": "a smiling hero in a plain costume flexing huge arms, lifting a boulder",
    "an ice warrior": "a warrior in blue armour, frost and icicles forming around their fists",
    "a fire warrior": "a warrior in red armour, flames curling around their fists",
    "an invisible hero": "a hero fading to transparent, only a faint outline of the costume left",
    "a flying hero": "a hero in a plain costume flying upward, one fist forward",
    "a mind-reading hero": "a hero touching their temple, glowing swirls circling their head",
    "a time-freezing hero": "a hero holding up one palm while clocks hang frozen in the air",
    "a block-world builder": "a blocky cube-shaped character holding a pickaxe, chunky voxel style",
    "a battle-royale soldier": "a cheerful cartoon soldier in colourful gear with a backpack and parachute",
    "a caped flying hero": "a smiling caped hero flying with one fist forward, plain blue and red costume",
    "a masked night vigilante": "a caped hero in a dark grey cowl and mask crouched on a rooftop",
    "a wall-crawling hero": "a hero in a plain red and blue suit crouching on a wall",
    "a hero in powered armour": "a hero in bulky red and gold robot armour with a glowing chest light",
    "a robot army": "a squad of friendly boxy robots marching in a row",
    "a dinosaur army": "a herd of cartoon dinosaurs charging forward together",
    "an alien": "a friendly little green alien with big black eyes",
    "a robot": "a friendly boxy cartoon robot with an antenna",
    "sharks": "a grey shark with a white belly swimming",
    "dinosaurs": "a green tyrannosaurus rex roaring",
    "a lion": "a male lion with a full golden mane",
    "a gorilla": "a big black gorilla beating its chest",
    "a giant squid": "a huge purple squid with long curling tentacles",
    "a cheetah": "a slender spotted cheetah running",
    "an eagle": "a brown eagle with wings spread wide",
    "a grizzly bear": "a large brown grizzly bear rearing up",
    "a crocodile": "a green crocodile with a long toothy snout",
    "a rhino": "a grey rhino with one big horn",
    "a dragon": "a friendly green dragon puffing a small flame",
    "a phoenix": "a bird made of orange flame with glowing wings",
    "a wizard": "a wizard in a blue pointed hat holding a glowing staff",
    "a knight": "a knight in shining silver armour with a sword and shield",
    "a unicorn": "a white unicorn with a rainbow mane and a golden horn",
    "a griffin": "a griffin, eagle head and wings on a lion's body",
    "a giant": "a huge friendly giant towering over little trees",
    "a ninja": "a ninja in a black outfit and mask",
    "a pirate": "a cheerful cartoon pirate in a hat with an eyepatch",
    "a werewolf": "a friendly cartoon wolf-man standing upright",
    "a vampire": "a cartoon vampire in a black cape with small fangs",
    # swarm vs one — the picture shows MANY / ONE, never a countable number (image
    # models can't count; the number is on the card, not in the art).
    "100 house cats": "a big crowd of many house cats gathered together",
    "1 tiger": "one large orange tiger with black stripes, snarling",
    "3 gorillas": "a small group of muscular gorillas standing together",
    "1 megalodon": "one enormous prehistoric megalodon shark with huge jaws",
    "50 humans": "a large crowd of ordinary cartoon people standing together",
    "1 silverback gorilla": "one huge silverback gorilla with a grey back, beating its chest",
    "1,000 rats": "a huge swarm of small brown rats",
    "1 elephant": "one big grey elephant with tusks and a raised trunk",
    "10 wolves": "a pack of grey wolves standing together, snarling",
    "1 grizzly bear": "one large brown grizzly bear rearing up on its hind legs",
    "100 chickens": "a big flock of many white and brown chickens",
    "1 crocodile": "one big green crocodile with a long toothy snout",
    "5 lions": "a pride of golden lions standing together",
    "1 t-rex": "one green tyrannosaurus rex roaring, big head and tiny arms",
    "100 kids": "a big cheerful crowd of cartoon children",
    "1 gorilla": "one huge muscular gorilla beating its chest",
    "1,000 bees": "a big buzzing swarm of yellow and black bees",
    "1 bear": "one large brown bear standing",
    "20 raptors": "a pack of green velociraptors running together",
    "100 caped heroes": "a big group of smiling caped superheroes in plain colourful costumes",
    "100 masked ninjas": "a big group of ninjas in black outfits and masks",
    "50 knights": "a group of knights in shining silver armour holding swords and shields",
    "1 dragon": "one big green dragon breathing a burst of fire",

    # ---- THIS OR THAT --------------------------------------------------------
    "dragon": "a friendly green dragon",
    "unicorn": "a white unicorn with a rainbow mane",
    "wizard": "a wizard in a pointed hat with a glowing staff",
    "superhero": "a smiling hero in a plain colourful costume and cape",
    "flying": "a happy kid flying through the sky, arms stretched out",
    "invisibility": "a child turning see-through, only a faint outline showing",
    "magic wand": "a glowing magic wand trailing sparkles",
    "magic sword": "a sword glowing with blue magic energy",
    "mermaid": "a smiling mermaid with a shiny green tail",
    "fairy": "a tiny fairy with sparkling translucent wings",
    "robot friend": "a friendly cartoon robot waving hello",
    "alien friend": "a friendly green alien waving hello",
    "time machine": "a shiny machine with a big clock face and levers",
    "teleporter": "a glowing blue portal ring with swirling light inside",
    "candy world": "a landscape of lollipop trees and gumdrop hills",
    "toy world": "a landscape built from toy blocks and stuffed animals",
    "magic castle": "a sparkling fairytale castle with tall pointed towers",
    "rocket ship": "a red and white rocket ship blasting off",
    "talking dog": "a happy cartoon dog mid-bark with little speech sparkles",
    "talking cat": "a happy cartoon cat mid-meow with little speech sparkles",
    "pet dinosaur": "a small friendly baby dinosaur on a lead",
    "pet dragon": "a small friendly baby dragon sitting",
    "ice powers": "a hand shooting a beam of ice and snowflakes",
    "fire powers": "a hand shooting a beam of fire",
    "turn giant": "a kid grown enormous, towering over tiny houses",
    "turn tiny": "a tiny kid standing beside a normal apple, dwarfed by it",
    "treasure map": "an old rolled parchment map marked with a red X",
    "magic key": "an ornate golden key glowing with sparkles",
    "super speed": "a kid running flat out with speed lines behind them",
    "super strength": "a kid flexing huge arms, lifting a boulder overhead",
    "pirate ship": "a wooden pirate ship with black sails",
    "space station": "a space station orbiting, solar panels spread wide",
    "phoenix": "a bird made of orange flame with glowing wings",
    "griffin": "a griffin, eagle head and wings on a lion's body",
    "invisible cloak": "a flowing cloak with the wearer fading transparent beneath it",
    "flying carpet": "a patterned magic carpet floating in the air",
    "pizza that never runs out": "an impossibly tall stack of pizza slices",
    "a burger the size of a car": "a giant cheeseburger as big as a car with a tiny kid beside it",
}


def _slug(s: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:44]
    return f"{base}_{hashlib.sha1(s.lower().encode()).hexdigest()[:6]}"


def visual_for(option_text: str, hint: str | None = None) -> str:
    """The concrete thing to draw for this option."""
    return hint or ART_HINTS.get(option_text.strip().lower()) or option_text



# What each cached picture was actually drawn FROM. Without this the cache is keyed
# by the option's name alone, so improving a hint changes nothing — the old image is
# returned forever. That is how a ringed planet stayed on the "Jupiter" card after
# the hint was fixed. A recorded prompt that no longer matches means the picture is
# stale and must be redrawn.
MANIFEST = os.path.join(CACHE, "prompts.json")


def _manifest() -> dict:
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001 - a missing/corrupt manifest must not break art
        return {}


def _remember(slug: str, prompt: str) -> None:
    m = _manifest()
    m[slug] = prompt
    try:
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=1, sort_keys=True, ensure_ascii=False)
    except OSError:
        pass


def looks_right(path: str, subject: str) -> bool | None:
    """Does this picture actually show `subject`? None = couldn't check.

    Every failure this channel has shipped came from a picture nobody looked at: a
    ringed planet (Saturn) labelled "Jupiter", a family of three illustrating the
    answer "7", a wine bottle for "potato chips". Pool art can be reviewed by eye
    before it's committed — but questions Claude invents each morning have their art
    drawn in the cloud minutes before posting, so no human ever sees it first.

    So the bot looks instead. Cheap (one Haiku call per new picture) and it only runs
    on art that has never been reviewed.
    """
    try:
        import base64

        import anthropic
        import generate
        key = generate._api_key()
        if not key:
            return None
        with open(path, "rb") as f:
            blob = base64.standard_b64encode(f.read()).decode()
        msg = anthropic.Anthropic(api_key=key).messages.create(
            model=generate.MODEL, max_tokens=16, temperature=0,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/jpeg", "data": blob}},
                {"type": "text", "text": (
                    f"This picture is supposed to show: {subject}\n\n"
                    "Does it clearly and unmistakably show THAT? Answer NO if it shows a "
                    "different subject (a ringed planet when Jupiter was asked for), if the "
                    "number of things shown is wrong, if it has garbled text in it, or if it "
                    "is not cheerful and safe for a young child.\n"
                    "Reply with exactly YES or NO.")},
            ]}],
        )
        said = "".join(b.text for b in msg.content
                       if getattr(b, "type", "") == "text").strip().upper()
        return said.startswith("YES")
    except Exception:  # noqa: BLE001 - the check must never break a render
        return None


def is_stale(option_text: str, hint: str | None = None) -> bool:
    """True if the cached picture was drawn from a DIFFERENT prompt than we'd use now.

    Files with no manifest entry predate this record and are left alone — they were
    reviewed by eye under the old prompt, and regenerating all of them would ship
    hundreds of pictures nobody has looked at.
    """
    slug = _slug(option_text)
    if not os.path.exists(os.path.join(CACHE, slug + ".jpg")):
        return False
    was = _manifest().get(slug)
    return was is not None and was != STYLE.format(visual_for(option_text, hint))


# Freshly-drawn art is vision-checked before it's trusted (see looks_right). The
# committed pool is NOT re-checked: it was reviewed by eye, and a check costs an API
# call. VERIFY_ART=0 disables the check (e.g. offline) — new art then falls through
# unverified rather than blocking a render.
VERIFY_ART = os.getenv("VERIFY_ART", "1") != "0"


def fetch(option_text: str, hint: str | None = None) -> str | None:
    """A local cartoon sticker for this option, or None. Never raises."""
    if not option_text:
        return None
    os.makedirs(CACHE, exist_ok=True)
    slug = _slug(option_text)
    path = os.path.join(CACHE, slug + ".jpg")
    prompt = STYLE.format(visual_for(option_text, hint))
    if os.path.exists(path):
        was = _manifest().get(slug)
        if was is None or was == prompt:
            return path                      # unchanged (or legacy) — keep it
        # the hint changed: the cached picture is answering the old question

    subject = visual_for(option_text, hint)
    # Seed from the option so an image is stable across runs (and so Pollinations'
    # own cache can serve a repeat instantly instead of re-generating).
    seed = int(hashlib.sha1(option_text.lower().encode()).hexdigest()[:6], 16) % 100000
    from PIL import Image
    # The endpoint is free and strict: it 500s intermittently, and it 429s hard if
    # you push it. Six parallel workers got 198/200 rejected, so requests must stay
    # SERIAL and back off. A 429 means "wait", not "give up" — retrying too eagerly
    # just extends the throttle. Each seed also gets ONE vision-check; a wrong
    # picture (Saturn for Jupiter) is discarded and the next seed tried.
    for attempt in range(RETRIES):
        url = (ENDPOINT + urllib.parse.quote(prompt)
               + f"?width=512&height=512&nologo=true&safe=true&seed={seed + attempt}")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=TIMEOUT) as r:
                blob = r.read()
            if len(blob) < 2000:      # an error page, not an image
                time.sleep(BACKOFF)
                continue
            with open(path, "wb") as f:
                f.write(blob)
            with Image.open(path) as im:
                im.verify()
            if VERIFY_ART and looks_right(path, subject) is False:
                os.remove(path)       # wrong subject — try a different seed
                continue
            _remember(slug, prompt)
            return path
        except Exception as e:  # noqa: BLE001 - art is never worth failing a render
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            code = getattr(e, "code", None)
            time.sleep(BACKOFF * (4 if code == 429 else 1) * (attempt + 1))
    return None


if __name__ == "__main__":
    import sys
    import content
    opts, seen = [], set()
    for fmt in content.FORMATS:
        for row in content.FORMATS[fmt][2]:
            for o in (row[1], row[2]) if fmt == "trivia" else (row[0], row[1]):
                if o and o.lower() not in seen:
                    seen.add(o.lower())
                    opts.append(o)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(opts)
    for i, o in enumerate(opts[:limit], 1):
        got = fetch(o)
        print(f"{i:3}/{min(limit,len(opts))} {'OK  ' if got else 'FAIL'} {o[:40]:40} <- {visual_for(o)[:44]}")
