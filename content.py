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
# two videos in a row can't land on the same topic. Step 3 is coprime with 8.
_TOPIC_FMT_OFFSET = {"wyr": 0, "this_or_that": 1, "rank": 2, "higher_lower": 3, "trivia": 4}

# NOT every topic works with every format, and pairing them freely ships nonsense.
# It really happened: "Who Would WIN? Owning every video game ever made vs Owning
# every pizza restaurant in town" — a would-you-rather wearing a battle's label,
# because the topic said "money" and a battle between two possessions is meaningless.
#
# So each format declares what it can actually host:
#   rank         needs two things that could FIGHT — creatures, heroes, powers.
#   higher_lower needs two things with a real, checkable SIZE.
#   trivia       needs a settled FACT, which rules out magic (there are no facts
#                about wizards) and powers.
# The two opinion formats are pure preference, so anything goes.
FORMAT_TOPICS = {
    "wyr": _TOPIC_KEYS,
    "this_or_that": _TOPIC_KEYS,
    "rank": ["animals", "magic", "powers", "gaming"],
    "higher_lower": ["animals", "space"],
    "trivia": ["animals", "space", "food", "school"],
}


def topics_for_format(fmt: str) -> list[str]:
    return FORMAT_TOPICS.get(fmt, _TOPIC_KEYS)


def topic_for(date: str, fmt: str = "") -> str:
    """The topic for this video — only one this format can actually host."""
    import datetime as _dt
    try:
        day = _dt.date.fromisoformat(str(date)[:10]).toordinal()
    except ValueError:
        day = sum(ord(c) for c in str(date))
    allowed = topics_for_format(fmt)
    return allowed[(day * 3 + _TOPIC_FMT_OFFSET.get(fmt, 0)) % len(allowed)]


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
    ("shrink to ant size", "grow to giant size", "🐜", "🦍"),
    ("only eat candy", "only eat chips", "🍬", "🍟"),
    ("breathe underwater", "walk through walls", "🌊", "🧱"),
    ("have super speed", "read minds", "💨", "🧠"),
    ("have a lightsaber", "have a magic wand", "⚔️", "🪄"),
    ("be a superhero", "be a wizard", "🦸", "🧙"),
    ("have night vision", "have x-ray vision", "🌙", "🦴"),
    ("live on the moon", "live underwater", "🌕", "🐠"),
    ("have a robot butler", "have a flying car", "🤖", "🚗"),
    ("turn invisible", "turn into any animal", "🫥", "🐯"),
    ("have unlimited pizza", "have unlimited tacos", "🍕", "🌮"),
    ("have a pet penguin", "have a pet monkey", "🐧", "🐵"),
    ("have a treehouse", "have a secret underground base", "🌳", "🕳️"),
    ("have wings", "have a tail", "🪽", "🦎"),
    ("time travel to the past", "time travel to the future", "⏪", "⏩"),
    ("have a chocolate river", "have a candy mountain", "🍫", "🍭"),
    ("be super lucky", "be super smart", "🍀", "🧠"),
    ("have a pet unicorn", "have a pet phoenix", "🦄", "🔥"),
    ("never have to sleep", "never have to eat", "😴", "🍽️"),
    ("have a magic carpet", "have a hoverboard", "🧞", "🛹"),
    ("swim like a fish", "run like a cheetah", "🐟", "🐆"),
    ("own a candy store", "own a toy store", "🍬", "🧸"),
    ("be able to teleport", "be able to freeze time", "🌀", "⏱️"),
    ("have a dinosaur as a pet", "ride a dragon to school", "🦕", "🐉"),
    ("have a pool full of jelly", "a pool full of slime", "🟢", "🫧"),
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
    ("have glow-in-the-dark skin", "color-changing hair", "✨", "🌈"),
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

# --- vetted daydream set --------------------------------------------------
# Written per-topic and then run past a harsh editor that rejected anything a kid
# already has an answer to. Rows here are 6-wide: the last two are the PICTURE for
# each option, written alongside the question, because an image model can't draw an
# idea like "never do homework again" from the text alone.
WYR_VETTED = [
    # --- food ------------------------------------------------------
    ("Gum that lets you fly", "A lollipop that turns you invisible", "🍬", "🍭",
     "A grinning kid blowing a huge bubble, feet lifted off the ground, floating above the rooftops of their street with a dog barking below",
     "A see-through kid at a birthday party — only their sneakers and a swirly lollipop are visible, while confused grown-ups look around"),
    ("A chocolate river in your backyard", "A cotton candy cloud bed", "🍫", "🍧",
     "A kid in swim trunks floating on an inner tube down a brown chocolate river winding past a garden fence, cupping a handful to drink",
     "A kid in pyjamas lying on a fluffy pink cotton candy cloud floating outside their bedroom window, pulling off a piece to eat"),
    ("A cookie that grants one wish", "A donut you teleport through", "🍪", "🍩",
     "A kid biting a glowing golden cookie as sparkles pour out and a shooting star curls around their head",
     "A kid stepping through the hole of a giant sprinkled donut, one leg in their bedroom and one leg out in a jungle full of parrots"),
    ("A slushie that freezes anything", "A chili that gives fire breath", "🥤", "🌶️",
     "A kid pointing a blue slushie cup at a puddle, an icy beam turning it into a shining skating rink",
     "A kid holding a red chili pepper and breathing a big orange flame that toasts a marshmallow on a stick"),
    ("Cupcakes that hatch into pets", "Popcorn that makes movies real", "🧁", "🍿",
     "A cupcake cracking open on a plate as a tiny frosting-covered creature with big eyes and little legs hops into a kid's cupped hands",
     "A kid on a couch holding a popcorn bucket while a superhero and a spaceship burst out of the TV into the living room"),
    ("Ice cream that gives you superpowers", "Honey that makes animals talk", "🍦", "🍯",
     "A kid at an ice cream counter holding a triple cone — one scoop crackling with lightning, one sprouting little wings, one flexing a muscle",
     "A kid sitting on grass with a honey jar, mid-conversation with a squirrel, a deer and a pigeon who all have speech bubbles"),
    ("A cake that makes you giant", "A grape that shrinks you tiny", "🎂", "🍇",
     "A kid as tall as an apartment block, standing in the street holding a slice of cake, waving at people in a window",
     "A thumb-sized kid in a grass forest riding a bumblebee like a horse, next to a grape the size of a boulder"),
    ("Live in a gingerbread castle", "A swimming pool of ice cream", "🏰", "🍨",
     "A kid waving from the tower window of a gingerbread castle with gumdrop bricks and icing turrets, having taken a bite out of the door",
     "A kid floating on a pool ring in a backyard pool filled with swirly ice cream, holding a shovel-sized spoon"),
    ("Ride a flying pancake to school", "A watermelon house with a slide", "🥞", "🍉",
     "A kid sitting cross-legged on a giant pancake with a butter pat on it, flying over a school bus and waving down at the kids inside",
     "A house-sized watermelon with a round door and windows cut in it, a kid whooshing out of a slide made of pink watermelon flesh"),
    ("Ride your own bubblegum bubble", "Milk that lets you pick dreams", "🎈", "🥛",
     "A kid perched on top of a giant pink bubblegum bubble drifting over a town park, still chewing",
     "A kid asleep in bed with an empty milk glass on the nightstand and a big dream bubble above them showing them riding a dragon"),
    ("Endless pizza, everything else tastes plain", "Every food amazing, pizza gone forever", "🍕", "🍽️",
     "A kid sitting on a mountain of open pizza boxes eating a slice, while a grey lifeless carrot sits on a plate at the bottom",
     "A kid at a glowing feast table piled with tacos, sushi and burgers, watching a ghostly pizza slice float away out the window"),
    # --- powers ----------------------------------------------------
    ("fly to school every morning", "turn invisible whenever you want", "☁️", "🫥",
     "a grinning kid with a backpack flying above the rooftops, birds flapping alongside them",
     "a laughing kid in a school hallway whose arm and legs have faded away, leaving a backpack floating in midair"),
    ("chat with every animal alive", "hear what anyone is thinking", "🐶", "💭",
     "a kid sitting cross-legged on grass mid-conversation with a dog, a squirrel and a parrot all leaning in to listen",
     "a kid smirking at a lunch table as thought bubbles pop up over three classmates' heads showing what they really think"),
    ("outrun a speeding race car", "blink anywhere in the world", "👟", "🌀",
     "a blurred kid sprinting past a race car on a track, leaving streaks of fire on the road behind them",
     "a kid stepping out of a glowing swirling portal in their bedroom wall and onto a sunny beach"),
    ("pause time with one snap", "rewind the last ten minutes", "⏱️", "⏪",
     "a kid strolling through a classroom snapping their fingers while papers and a thrown paper ball hang frozen in midair",
     "a kid grinning as a spilled milkshake leaps back up off the floor into the glass in their hand"),
    ("shrink smaller than an ant", "grow taller than a skyscraper", "🐜", "🏙️",
     "a tiny kid riding a beetle like a horse through towering blades of grass",
     "a giant grinning kid standing between skyscrapers with a helicopter hovering beside their shoulder"),
    ("breathe underwater like a fish", "walk straight through any wall", "🐠", "🧱",
     "a kid sitting on the ocean floor chatting with a school of fish, a sea turtle beside them, bubbles rising",
     "a kid stepping halfway through a brick wall, top half already inside the kitchen reaching for a cookie jar"),
    ("lift a school bus overhead", "move things with your mind", "🚌", "🧠",
     "a kid holding a yellow school bus above their head with one hand while classmates cheer from the sidewalk",
     "a kid lounging on a couch with one hand raised as the remote, a popcorn bowl and a soda float through the air toward them"),
    ("turn into any animal", "make five copies of yourself", "🐯", "👥",
     "a kid in the backyard mid-transformation into a tiger, one half still a kid, the other half striped fur and paw",
     "five identical kids in one bedroom: one doing homework, one washing dishes, one gaming, one skateboarding, one napping"),
    ("shoot lightning from your fingers", "swing on webs you shoot", "⚡", "🕸️",
     "a kid on a hilltop at night with arms raised and bright lightning crackling between their fingertips",
     "a kid swinging on a white web line strung between two tall city buildings, feet kicked out, huge grin"),
    ("stretch your arms a mile", "bounce like unbreakable rubber", "🖐️", "🏀",
     "a kid on the couch whose arm stretches across the whole room and around the corner to grab cookies off the kitchen counter",
     "a kid boinging off the sidewalk high over a parked car, body squished like a rubber ball, laughing"),
    ("climb walls like a gecko", "jump over a whole building", "🦎", "🦘",
     "a kid crawling straight up the brick outside of an apartment building, palms stuck flat to the wall, waving at a window",
     "a kid mid-leap arcing over an apartment building rooftop with birds scattering around them"),
    ("make it snow any day", "bend water like a ribbon", "❄️", "🌊",
     "a kid in shorts on a green summer lawn with a small snow cloud above them and a finished snowman beside them",
     "a kid at a pool lifting a long ribbon of water out of it and curling it through the air with one hand"),
    # --- animals ---------------------------------------------------
    ("a baby dragon in your backpack", "a baby T-rex on a leash", "🐉", "🦖",
     "a small green dragon poking its head out of an unzipped school backpack on a kid's shoulders, tiny wings folded, puff of smoke from its nose",
     "a smiling kid walking a knee-high cartoon T-rex on a red leash down a sidewalk past a fire hydrant"),
    ("understand every animal alive", "turn into any animal you want", "🦜", "🦊",
     "a kid sitting cross-legged on grass while a squirrel, a pigeon and a dog all talk at once, each with a speech bubble",
     "a kid mid-transformation into a fox, half boy and half fox, sparkles swirling in a spiral around him"),
    ("a talking wolf as your bodyguard", "a talking owl who knows secrets", "🐺", "🦉",
     "a huge grey wolf sitting shoulder-height beside a small kid at a bus stop, speech bubble saying hello",
     "an owl perched on a kid's shoulder leaning in to whisper, a speech bubble with a golden key inside it"),
    ("a woolly mammoth school bus", "a triceratops that plays fetch", "🦣", "🦕",
     "a woolly mammoth with a yellow bus sign on its side and four kids riding on its back, waving",
     "a triceratops running back to a kid with a giant stick in its mouth, tail wagging, in a park"),
    ("hatch a glowing dragon egg", "find a frozen baby yeti", "🥚", "🧊",
     "a kid in pajamas cupping a cracked, glowing egg on a bed as a tiny dragon snout pokes out",
     "a kid with a flashlight staring at a fuzzy white baby yeti curled up inside a block of blue ice in a cave"),
    ("turn into a cheetah after school", "turn into a shark on weekends", "🐆", "🦈",
     "a cheetah sprinting along a road beside a car, a dropped school backpack and shoes behind it",
     "a kid-sized shark cruising over a bright coral reef, sunbeams cutting through the water"),
    ("a talking horse that wins races", "a unicorn hiding in your garage", "🐴", "🦄",
     "a brown horse crossing a finish line with a kid on its back, speech bubble saying we won",
     "a white unicorn standing between a bike and a lawnmower in a garage, horn glowing, kid peeking through the door"),
    ("a friendly kraken in your pool", "a phoenix living in your fireplace", "🐙", "🔥",
     "a giant purple octopus filling a backyard pool, one tentacle handing a kid a pool noodle",
     "a glowing orange firebird perched on the logs inside a living room fireplace, watched by a kid on the rug"),
    ("a dinosaur park in your backyard", "a dragon cave under your house", "🦕", "🐲",
     "a fenced backyard with a brachiosaurus eating from a tree and two small dinos running past a swing set",
     "a kid on a ladder going down through a trapdoor into a glowing cave where a big dragon sleeps on gold coins"),
    ("a bear that gives piggyback rides", "a gorilla that builds you treehouses", "🐻", "🦍",
     "a huge brown bear walking through a forest with a laughing kid riding on its shoulders",
     "a gorilla hammering the last plank onto a giant treehouse while a kid climbs the rope ladder"),
    ("a turtle who tells 500-year-old stories", "a crow that brings you treasure", "🐢", "🐦",
     "an ancient giant tortoise on a beach at sunset with three kids sitting on the sand listening, speech bubble showing a pirate ship",
     "a black crow landing on a windowsill dropping a gold ring onto a pile of coins and marbles, kid grinning"),
    ("grow real dragon wings", "grow a monkey tail", "🪽", "🐒",
     "a kid hovering above a backyard with big red dragon wings spread out of slits in their t-shirt",
     "a kid hanging upside down from a tree branch by a long curly tail, holding an ice cream in both hands"),
    # --- gaming ----------------------------------------------------
    ("Live inside your favorite game", "Your game hero moves in", "🎮", "🛡️",
     "a kid standing inside a blocky pixel world holding a pickaxe, grinning as square clouds float past a square sun",
     "a huge armored video-game hero squeezing through a kid's bedroom doorway carrying a suitcase, high-fiving the kid"),
    ("Respawn after every mistake", "Pause real life anytime", "🚩", "⏸️",
     "a kid reappearing in a burst of blue sparkles beside a glowing checkpoint flag, their crashed bike lying in the grass nearby",
     "a kid strolling casually through a classroom where every classmate and a thrown paper plane hang frozen in mid-air"),
    ("Place real blocks with your hands", "Pocket portal door anywhere", "🧱", "🚪",
     "a kid standing on a floating grass block, pressing a glowing stone block into the empty air to build a bridge over their street",
     "a kid stepping through a swirling orange portal opened on their bedroom wall, with sand and palm trees on the other side"),
    ("Unlock double jump forever", "Run at Sonic speed", "🦘", "👟",
     "a kid high above rooftops bouncing off a small puff of white light for a second jump, sneakers kicking, arms out",
     "a kid blurring down a street past parked cars with blue lightning trails streaming off their heels and leaves swirling behind"),
    ("Real go-kart with item boxes", "Rocket car that plays soccer", "🏎️", "⚽",
     "a kid drifting a bright go-kart around the corner of their own street, a floating question-mark box hovering just ahead",
     "a kid in a rocket-powered car flying through the air with flames behind, smacking a giant soccer ball toward a huge goal"),
    ("Ride your game's pet dragon", "Robot sidekick follows you everywhere", "🐉", "🤖",
     "a kid with a backpack riding a friendly green dragon over their school, the dragon's wings spread wide",
     "a small floating robot with big glowing eyes hovering beside a kid on the sidewalk, carrying their lunchbox"),
    ("Fast travel anywhere instantly", "Fly in real creative mode", "🗺️", "☁️",
     "a kid stepping out of a glowing blue ring in front of the Eiffel Tower, their bedroom still visible through the ring",
     "a kid hovering cross-legged in the sky above a blocky world, placing a floating block with one finger"),
    ("Homework becomes a boss battle", "Your town becomes open world", "✏️", "🧭",
     "a kid holding a glowing pencil like a sword, facing a giant grumpy cartoon math worksheet with arms and a health bar",
     "a kid standing on a hilltop looking over their whole town, glowing yellow quest markers floating above the houses"),
    ("Save your game before tests", "Extra life in your pocket", "💾", "🍄",
     "a kid at a school desk pressing a big glowing floppy-disk button that floats above their blank test paper",
     "a kid holding a glowing green 1-UP style mushroom in their palm, half-tucked into a jacket pocket"),
    ("Grappling hook on your wrist", "Jetpack you spawn anytime", "🪝", "🚀",
     "a kid firing a glowing grappling hook from a wristband and swinging between two rooftops over a street",
     "a kid blasting up above the treetops on a chunky blocky jetpack, orange flames shooting out below their feet"),
    # --- magic -----------------------------------------------------
    ("Ride a griffin over mountains", "Race a unicorn through clouds", "🦅", "🦄",
     "a kid gripping the neck feathers of a huge griffin as it soars above snowy mountain peaks",
     "a kid riding a galloping white unicorn that leaves a rainbow trail across fluffy clouds"),
    ("Closet door to any world", "Blink and teleport anywhere", "🚪", "✨",
     "a kid pushing open a closet door with coats hanging beside it, a glowing jungle full of vines on the other side",
     "a kid vanishing into a puff of sparkles on a sidewalk and reappearing beside a castle on the other side of the picture"),
    ("Cloak that turns you invisible", "Boots that let you fly", "🧥", "🥾",
     "a kid pulling a shimmering silver cloak over their shoulders in a school hallway, their legs already invisible",
     "a kid in glowing boots hovering high above their neighborhood rooftops with arms stretched out"),
    ("Baby dragon in your pocket", "Phoenix chick that never dies", "🐲", "🪶",
     "a tiny green dragon poking its head out of a kid's hoodie pocket and puffing a small smoke ring",
     "a kid cupping a glowing orange phoenix chick with flame-tipped feathers in both hands"),
    ("Snap your fingers, freeze time", "Pocket watch that rewinds days", "⏳", "🕰️",
     "a kid snapping their fingers in a cafeteria where every classmate and a spilled drink hang frozen in mid-air",
     "a kid winding a golden pocket watch as its hands spin backward and the room behind them streaks into blurry lines"),
    ("Cauldron that brews any potion", "Beanstalk to a cloud castle", "🧪", "🌱",
     "a kid stirring a bubbling green cauldron with a long spoon, colorful bottles and an open recipe scroll beside it",
     "a kid climbing a giant twisting beanstalk toward a stone castle sitting on a cloud"),
    ("Shrink into a winged fairy", "Mermaid tail for ocean swimming", "🧚", "🧜",
     "a kid shrunk to the size of a teacup with glowing dragonfly wings, standing on a daisy petal",
     "a kid with a shimmering blue-green mermaid tail swimming past a coral reef full of striped fish"),
    ("Shapeshift into any animal", "Dragon wings on your back", "🐺", "🪽",
     "a kid mid-transformation into a wolf, half kid and half wolf, with sparkles swirling where the fur meets skin",
     "a kid lifting off a school field as huge red dragon wings unfold from their back, backpack dangling"),
    ("Paintbrush whose drawings come alive", "Storybook you can walk into", "🖌️", "📕",
     "a kid painting a horse on paper as the same horse gallops off the page and across the desk",
     "a kid stepping one leg into a giant open storybook where a pirate ship sails between the pages"),
    # --- space -----------------------------------------------------
    ("Fly your own rocket ship", "Drive your own submarine", "🚀", "🛥️",
     "a grinning kid in a space helmet gripping the controls of a small rocket, stars and a planet out the round window",
     "a grinning kid steering a small yellow submarine past a coral reef, bright fish crowding the porthole"),
    ("Pocket-sized pet alien", "Baby octopus best friend", "👽", "🐙",
     "a tiny purple three-eyed alien peeking out of a kid's hoodie pocket while the kid smiles down at it",
     "a small blue octopus sitting on a kid's head underwater, tentacles draped over their swim goggles"),
    ("Build a secret moon base", "Build a secret underwater base", "🌕", "🫧",
     "a kid in a spacesuit standing at the door of a silver dome base on grey moon craters, blue Earth in the black sky",
     "a kid inside a glass dome base on the sandy seafloor, waving at a passing school of fish outside"),
    ("Ride a whale to school", "Ride a comet across the sky", "🐋", "☄️",
     "a kid with a backpack sitting on the back of an enormous blue whale gliding toward a school on the shore",
     "a kid crouched on a glowing rock with a long fiery tail, streaking above rooftops at night"),
    ("Discover a brand-new planet", "Find a sunken treasure ship", "🪐", "⚓",
     "a kid in a spacesuit planting a flag on a swirly striped purple planet with three moons above",
     "a kid in a diving mask floating beside a broken wooden ship on the seafloor, gold coins spilling from a cracked chest"),
    ("Speak every alien language", "Talk to every sea creature", "🛸", "🐠",
     "a kid sitting cross-legged on red sand chatting with three different aliens around a glowing lamp, saucer parked behind",
     "a kid underwater in a swim mask laughing mid-conversation with a sea turtle and a striped fish"),
    ("Sleep in a zero-gravity bedroom", "Shark tunnel through your bedroom", "🛏️", "🦈",
     "a kid in pajamas floating upside down in mid-air in their bedroom, pillow, sneakers and teddy bear drifting around them",
     "a kid lying in bed inside a clear glass tunnel with two big sharks cruising overhead"),
    ("Robot buddy on Mars", "Dolphin best friend", "🤖", "🐬",
     "a kid in a spacesuit high-fiving a small round robot on red rocky ground, tiny Sun low in the sky",
     "a kid holding a dolphin's fin as it leaps out of the ocean, both mid-air and grinning"),
    ("Camp on a space station", "Camp on the ocean floor", "🛰️", "🦀",
     "a kid in a sleeping bag strapped to the wall of a space station, snacks floating nearby, Earth glowing out the window",
     "a kid in a glowing dome tent on the sandy seafloor, a sea turtle drifting past the opening"),
    ("Skateboard across the moon", "Ride a squid like a jet-ski", "🛹", "🦑",
     "a kid in a spacesuit mid-kickflip on a skateboard high above grey moon craters, stars behind",
     "a kid gripping a big squid as it rockets through the water leaving a long trail of bubbles"),
    ("Telescope that spots alien cities", "Flashlight that lights the deep trench", "🔭", "🔦",
     "a kid at a telescope on a rooftop, seeing a glowing alien city of towers on a distant planet in the eyepiece view",
     "a kid in a diving suit shining a huge beam down a dark trench, revealing an enormous friendly glowing fish"),
    ("Plant the first flag on Mars", "First kid to the deepest trench", "🚩", "🧭",
     "a kid in a spacesuit pushing a flag into a red rocky hill, rover and rocket parked below",
     "a kid inside a round glass deep-sea sub touching down on black trench sand, one tiny glowing creature in the light"),
    # --- money -----------------------------------------------------
    ("swim in a pool of gold", "grow a money tree outside", "🪙", "🌳",
     "a grinning kid doing a cannonball into a swimming pool filled to the brim with gold coins, coins splashing up around them",
     "a kid on tiptoes picking dollar bills off a leafy backyard tree, a basket at their feet already overflowing with cash"),
    ("buy an entire theme park", "own a whole candy factory", "🎢", "🍬",
     "a kid holding an oversized golden key standing at the open gates of a theme park, a looping rollercoaster behind them",
     "a kid in a hard hat standing on a catwalk above candy conveyor belts, lollipops and gumballs rolling past below"),
    ("sleep on a dragon's gold hoard", "captain a treasure-stuffed pirate ship", "🐉", "🚢",
     "a kid in pyjamas curled up asleep on a huge mound of gold coins inside a cave, a friendly dragon dozing beside them",
     "a kid in a pirate hat gripping the ship's wheel, open treasure chests spilling jewels across the wooden deck"),
    ("own the world's biggest toy store", "own the world's biggest arcade", "🧸", "🕹️",
     "a kid pushing a shopping cart piled high with toys down a toy store aisle that stretches out of sight",
     "a kid holding a giant OPEN sign inside a dark arcade packed wall to wall with glowing game machines"),
    ("buy your school, add waterslides", "buy your street, add a racetrack", "🏫", "🏎️",
     "a kid whooshing down a blue waterslide that spirals out of a school's front doors",
     "a kid driving a go-kart down a suburban street lined with checkered flags and cheering neighbours"),
    ("a solid gold robot butler", "an elephant with jeweled tusks", "🤖", "🐘",
     "a shiny gold robot carrying a tray of snacks and a drink to a kid lounging on a couch",
     "a kid riding on the back of an elephant with sparkling jeweled tusks down a city street"),
    ("a castle with a hundred rooms", "your own diamond rocket ship", "🏰", "🚀",
     "a kid standing at the door of an enormous castle holding a huge ring of keys, dozens of lit windows above",
     "a kid waving from the hatch of a sparkling diamond rocket standing on a launchpad"),
    ("buy every video game ever made", "a mansion built from LEGO bricks", "🎮", "🧱",
     "a kid sitting cross-legged on top of a mountain of video game boxes, controller in hand",
     "a kid standing proudly in front of a two-storey mansion built entirely from giant LEGO bricks"),
    ("a cash machine in your bedroom", "a fountain that pours diamonds", "🏧", "⛲",
     "a kid pressing buttons on an ATM built into their bedroom wall as banknotes spit out into their hands",
     "a kid cupping both hands under a stone fountain that pours sparkling diamonds instead of water"),
    ("a helicopter that rains candy", "presents piled higher than your house", "🚁", "🎁",
     "a helicopter tipping a huge bucket of wrapped candy over a backyard while a kid stands below with arms raised",
     "a tiny kid standing at the base of a towering pile of wrapped presents that rises past their rooftop"),
    ("a rollercoaster through your house", "a waterslide from your bedroom window", "🎢", "🛝",
     "a rollercoaster car with a happy screaming kid inside looping through a living room past the sofa and TV",
     "a kid launching off a waterslide that starts at their bedroom window and splashes into a backyard pool"),
    # --- school ----------------------------------------------------
    ("a pencil that does homework", "a notebook that answers anything", "✏️", "📓",
     "a yellow pencil standing upright on its tip, writing neat answers on a worksheet by itself, while a grinning kid leans back in the chair with hands behind their head",
     "a kid whispering into an open glowing notebook as golden handwriting appears across the page on its own"),
    ("ride a dragon to school", "jetpack instead of the bus", "🐉", "🚀",
     "a kid in a backpack riding a green dragon that is landing on the school playground, other kids pointing up in amazement",
     "a kid wearing a jetpack shooting up over a yellow school bus stuck in traffic, leaving two puffs of smoke"),
    ("a classroom inside a volcano", "a classroom under the ocean", "🌋", "🐙",
     "kids at desks inside a hollow volcano, glowing orange lava bubbling behind a glass wall, teacher writing on a stone chalkboard",
     "kids at desks inside a glass dome on the seafloor, an octopus and a whale drifting past the curved window"),
    ("a teacher who's secretly a wizard", "a teacher who's a talking tiger", "🧙", "🐯",
     "a teacher in a pointy hat waving a wand so chalk, books and pencils float in circles around the classroom while kids cheer",
     "a big orange tiger wearing glasses and a tie, standing on hind legs at the front of the classroom pointing at a chalkboard"),
    ("a dog that really eats homework", "a robot twin who does homework", "🐕", "🤖",
     "a fluffy dog chewing a math worksheet with paper scraps flying, a kid beside it shrugging happily with empty hands",
     "a robot shaped like a kid sitting at a desk writing homework, while the real kid sneaks out the door with a soccer ball"),
    ("recess that lasts until dinnertime", "a lunch tray that makes anything", "⏰", "🍕",
     "kids swinging and playing tag on a playground under an orange sunset sky, the school clock on the wall showing six o'clock",
     "a kid holding a lunch tray as pizza, tacos and a sundae pop up out of the empty compartments in a sparkle"),
    ("a desk that becomes a spaceship", "a locker leading to a jungle", "🛸", "🌴",
     "a school desk with glowing rockets under it lifting a kid up through the classroom ceiling toward stars",
     "a kid stepping through an open school locker into a leafy jungle with palm trees, a waterfall and a parrot"),
    ("a school bus that flies", "a slide from bed to class", "🚌", "🛝",
     "a yellow school bus with wings soaring above rooftops and clouds, kids waving out of the windows",
     "a kid in pajamas whooshing down a long curly slide that starts at a bunk bed and ends right at a classroom desk"),
    ("Friday field trips to the Moon", "a field trip to dinosaur times", "🌙", "🦖",
     "a line of kids in spacesuits bouncing across grey moon craters, a small school flag planted beside them and Earth in the sky",
     "kids with backpacks and clipboards standing in tall ferns looking up at a long-necked dinosaur chewing leaves"),
    ("learn to fly in gym class", "art class where drawings come alive", "🪽", "🖍️",
     "kids with feathery wings on their backs hovering above the gym floor while a coach with a whistle points upward",
     "a crayon drawing of a lion climbing out of the paper onto the art table while a kid watches wide-eyed"),
    ("a unicorn as the class pet", "a tiny elephant as class pet", "🦄", "🐘",
     "a small white unicorn with a rainbow mane standing in the corner of a classroom, kids petting it and feeding it apples",
     "a hand-sized grey elephant standing on a school desk, spraying a little water from its trunk while kids giggle"),
    ("a hoodie that turns you invisible", "a hall pass that works anywhere", "🧥", "🎫",
     "a kid pulling up a hoodie hood while their body fades to see-through in a school hallway, only sneakers still showing",
     "a kid holding a glowing golden hall pass while walking through a school door that opens onto a sunny beach"),
    ("a book you can jump into", "a globe that teleports you there", "📖", "🌍",
     "a kid diving headfirst into a giant open library book, splashing into a painted pirate sea on the page",
     "a kid touching a spinning classroom globe as a swirl of light lifts them toward the pyramids appearing behind them"),
]

# Only rows that describe their own artwork go live. The 71 older rows above have no
# art description, so their pictures are generated from the option text alone — the
# failure that drew a ringed planet (Saturn) for "Jupiter" and a family of three for
# the answer "7". They aren't deleted: give a row a_art/b_art and it airs again.
# 90 vetted rows at 2 posts a day is about 45 days of content, so there is no rush
# to cut corners here.
WYR = [r for r in (WYR + WYR_VETTED) if len(r) >= 6 and r[4] and r[5]]

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
    # NOT "Pizza vs Burgers": a real-world preference every kid already has an
    # answer to — nothing to imagine, nothing to argue about.
    ("Pizza that never runs out", "A burger the size of a car", "🍕", "🍔"),
    # NOT "Marvel vs DC": two live brands owned by Disney and Warner Bros, and the
    # art step would draw their actual characters onto a monetised card.
    ("A caped flying hero", "A masked night vigilante", "🦸", "🦇"),
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
    # NOT "how many continents": the 7-continent model is taught in the US/UK, but
    # the 5- and 6-continent models are taught across Latin America and much of
    # Europe. "5" is a real answer for a real slice of the audience, so marking it
    # wrong is arguable, not checkable.
    ("How many legs does a crab have?", "10", "8"),
    ("What is the biggest ocean?", "Pacific", "Atlantic"),
    # NOT "largest desert -> Antarctica": true only under the low-precipitation
    # definition, and the pool's own rule below forbids trick questions. Sahara is
    # what every kid, teacher and parent will answer — and it IS the largest hot
    # desert. Telling a child they're wrong for saying it is the likeliest row in
    # this pool to earn an angry parent comment.
    ("What is the largest hot desert on Earth?", "Sahara", "Gobi"),
    # NOT "what gas do plants breathe in": "breathe in" conflates photosynthesis
    # with respiration. Plants respire too and do take in oxygen, so the "wrong"
    # answer is literally correct for the verb used. The ambiguity was in the
    # question, not the answer.
    ("What gas do plants use to make their food?", "Carbon dioxide", "Nitrogen"),
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
    ("An ostrich", "A penguin", "🐦", "🐧"),   # 🦤 is DODO, not an ostrich
    # NOT bare "A dolphin": the orca is the largest dolphin (~9m, 6t) and dwarfs a
    # great white, so a kid picturing one gets marked wrong for being right. The
    # species has to be named for the claim to hold.
    ("A great white shark", "A bottlenose dolphin", "🦈", "🐬"),
    # space
    ("The Sun", "The Earth", "☀️", "🌍"),
    ("Jupiter", "The Earth", "🪐", "🌍"),
    ("The Earth", "The Moon", "🌍", "🌕"),
    ("The Sun", "Jupiter", "☀️", "🪐"),
    # places / things
    ("Mount Everest", "The Eiffel Tower", "🏔️", "🗼"),
    # 🌏 faces the Pacific, 🌎 the Atlantic — a wave next to a globe read as two
    # different KINDS of thing rather than two comparable oceans.
    ("The Pacific Ocean", "The Atlantic Ocean", "🌏", "🌎"),
    ("Russia", "Australia", "🇷🇺", "🇦🇺"),
    ("A football pitch", "A tennis court", "⚽", "🎾"),
    ("A jumbo jet", "A school bus", "✈️", "🚌"),
    ("A skyscraper", "A house", "🏢", "🏠"),
]

# The card says WHO WOULD WIN, so every row must be a FIGHT: both sides have to be
# something a kid can picture squaring up, able to act, hit and lose. This pool was
# originally authored as "a fun which-is-better pair" — a different question — and
# that mismatch is what put "Who would win: Fortnite vs Minecraft" and bare powers
# like "Mind reading vs Time freezing" on a battle card. generate.py gates the rows
# Claude writes; nothing gated these, so they were the live half of the same bug.
# Named characters are out too: the pipeline generates monetised AI art of each
# option, and drawing Superman is someone else's copyright. Archetypes read the same
# to a kid and are ours.
RANK = [
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
    # powers — each power needs a BODY to wield it. "Super speed vs Super strength"
    # is two nouns that cannot fight; a fast hero vs a strong hero is a real fight
    # with the same appeal.
    ("A super-fast hero", "A super-strong hero", "⚡", "💪"),
    ("An ice warrior", "A fire warrior", "❄️", "🔥"),
    ("An invisible hero", "A flying hero", "🫥", "🦅"),
    ("A mind-reading hero", "A time-freezing hero", "🧠", "⏱️"),
    # heroes — archetypes, not anyone's characters
    ("A block-world builder", "A battle-royale soldier", "🧱", "🪂"),
    ("A caped flying hero", "A masked night vigilante", "🦸", "🦇"),
    ("A wall-crawling hero", "A hero in powered armour", "🕸️", "🦾"),
    ("A robot army", "A dinosaur army", "🤖", "🦖"),
    # space
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
# Which format each day gets. Would-you-rather appears 3x because it's the
# flagship and has by far the deepest question pool; the rest get one slot each.
# Which formats are LIVE, smallest-surface-first. Only would-you-rather has a pool
# where every airing row carries a reviewed art hint, so only it goes out. The other
# four are built and their bugs are fixed, but their pictures haven't been eyeballed
# yet — and this channel's failures have all come from shipping something nobody
# looked at. A format goes live when it has earned it, not when it exists.
#
# To bring one back: review its pictures (tools/contact_sheet.py), then add it here
# or set ENABLED_FORMATS="wyr,trivia" in the environment. Adding a name is all it
# takes; the rotation, topics and scheduling already handle it.
ENABLED_FORMATS = [f.strip() for f in os.getenv("ENABLED_FORMATS", "wyr").split(",") if f.strip()]

_FULL_ROTATION = ["wyr", "this_or_that", "wyr", "higher_lower", "wyr", "rank", "trivia"]
FORMAT_ROTATION = [f for f in _FULL_ROTATION if f in ENABLED_FORMATS] or ["wyr"]


def format_for(date: str, slot: int = 0) -> str:
    """The format for a given day.

    run.py used to default to "wyr" and nothing ever called this, so the channel
    would have posted would-you-rather EVERY day forever and the other four
    formats would never have aired. Stepping the date through the rotation is what
    actually makes it a five-format channel.
    """
    import datetime as _dt
    try:
        day = _dt.date.fromisoformat(str(date)[:10]).toordinal()
    except ValueError:
        day = sum(ord(c) for c in str(date))
    return FORMAT_ROTATION[(day + slot) % len(FORMAT_ROTATION)]


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
    # NB: "island" is deliberately NOT here. It put "own a private island vs own a
    # private jet" into a SPACE EDITION — which is neither space nor imaginative,
    # and it shipped in the channel's first ever video.
    "space": ("moon", "space", "rocket", "spaceship", "alien", "planet", "submarine",
              "underwater", "star", "galaxy", "astronaut"),
    "money": ("$", "money", "rich", "million", "dollar", "store", "jet", "gold",
              "mansion", "cash", "island", "billionaire", "lottery", "treasure chest"),
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
