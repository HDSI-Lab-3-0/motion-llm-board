# openrouter/wordbanks.py
"""
Spooky/classic Ouija word banks + keyword triggers.

Rules for this project:
- No MAYBE anywhere.
- YES/NO questions must answer only YES or NO.
- ONE_WORD answers should feel like a classic Ouija board: short, eerie, and spellable.
- Keep outputs short because the board physically spells them.
"""

YES_NO = ["YES", "NO"]

# ---------------------------
# Word banks (OUTPUTS)
# ---------------------------
WORD_BANKS = {
    # General spooky fallback
    "generic": [
        "WAIT", "WATCH", "LISTEN", "BEWARE", "NEAR", "HERE",
        "SOON", "LATER", "STAY", "LEAVE", "RETURN", "FOLLOW",
        "HIDDEN", "SECRET", "SHADOW", "SILENCE", "WHISPER",
        "NIGHT", "DARK", "COLD", "SIGN", "ANSWER", "TRUTH",
    ],

    # When they ask if someone/spirit is present
    "presence": [
        "HERE", "NEAR", "YES", "WATCH", "LISTEN", "WAIT",
        "CLOSER", "BEHIND", "BELOW", "ABOVE", "INSIDE",
        "SPIRIT", "SHADOW", "WHISPER",
    ],

    # Spirit / ghost / entity questions
    "spirit": [
        "SPIRIT", "GHOST", "SOUL", "SHADE", "ENTITY",
        "VISITOR", "STRANGER", "WANDERER", "WATCHER",
        "MOTHER", "FATHER", "CHILD", "FRIEND", "ENEMY",
    ],

    # Names / who is there
    # Simple eerie names so the board can spell them
    "names": [
        "ANNA", "MARY", "ELIZA", "CLARA", "EDEN", "NORA",
        "JAMES", "THOMAS", "SAMUEL", "ELIAS", "ISAAC",
        "RUTH", "MABEL", "AGNES", "VICTOR",
    ],

    # Places / where questions
    "places": [
        "HOUSE", "ROOM", "DOOR", "WINDOW", "ATTIC", "CELLAR",
        "HALL", "STAIRS", "MIRROR", "WOODS", "WATER", "GRAVE",
        "CHURCH", "GARDEN", "BENEATH", "BEHIND",
    ],

    # Time / when questions
    "time": [
        "NOW", "SOON", "TONIGHT", "MIDNIGHT", "DAWN", "DUSK",
        "THREE", "SEVEN", "NINE", "NEVER", "LATER", "AGAIN",
    ],

    # Warnings / danger
    "warning": [
        "BEWARE", "LEAVE", "STOP", "RUN", "HIDE", "WATCH",
        "COLD", "DARK", "DANGER", "CURSED", "BURIED",
        "LOCKED", "BROKEN", "BLOOD", "ASHES", "FIRE",
    ],

    # Advice / what should I do
    "advice": [
        "WAIT", "LEAVE", "STAY", "LISTEN", "WATCH", "ASK",
        "RETURN", "FOLLOW", "OPEN", "CLOSE", "HIDE",
        "SPEAK", "SILENCE", "TRUST", "DOUBT",
    ],

    # Love / relationship questions but spooky
    "relationships": [
        "LIES", "TRUTH", "WAIT", "LEAVE", "RETURN", "CALL",
        "TEXT", "SORRY", "FAITH", "DOUBT", "SECRET",
        "CLOSURE", "HEART", "ALONE",
    ],

    # Future / fate / destiny
    "future": [
        "SOON", "FATE", "CHANGE", "LOSS", "GAIN", "TRUTH",
        "SECRET", "PATH", "DOOR", "SIGN", "WARNING",
        "RETURN", "BEGIN", "END",
    ],

    # Dreams / nightmares
    "dreams": [
        "DREAM", "NIGHT", "SHADOW", "MIRROR", "VOICE",
        "DOOR", "WATCH", "SIGN", "MEMORY", "FEAR",
    ],

    # Death / afterlife, classic but not too graphic
    "afterlife": [
        "SOUL", "REST", "GRAVE", "ASHES", "BEYOND",
        "LIGHT", "DARK", "PEACE", "LOST", "FOUND",
        "RETURN", "REMEMBER",
    ],

    # Numbers / dates
    "numbers": [
        "ONE", "TWO", "THREE", "FOUR", "FIVE",
        "SIX", "SEVEN", "EIGHT", "NINE", "ZERO",
    ],

    # Goodbyes / ending the session
    "goodbye": [
        "GOODBYE", "LEAVE", "DEPART", "CLOSE", "END",
        "ENOUGH", "SILENCE", "RETURN",
    ],

    # Food / silly questions, but still spooky
    "food": [
        "SOUP", "BREAD", "TEA", "APPLE", "CAKE",
        "RICE", "PASTA", "RAMEN", "TACOS", "SUSHI",
        "NOODLES", "COFFEE", "MATCHA", "DUMPLINGS",
        "CURRY", "PIZZA",
    ],

    # Tech/debug questions, if someone asks the board about the machine
    "tech": [
        "RESET", "RETRY", "PORT", "WIRE", "POWER",
        "ERROR", "WAIT", "FIX", "SIGNAL",
    ],
}


# ---------------------------
# Keyword triggers (INPUTS)
# ---------------------------
KEYWORDS = {
    "presence": [
        "anyone here", "is anyone here", "are you here", "is somebody here",
        "is someone here", "are the spirits here", "spirit here",
        "ghost here", "with us", "in this room", "present"
    ],
    "spirit": [
        "spirit", "spirits", "ghost", "ghosts", "entity", "entities",
        "demon", "haunted", "dead", "soul", "who are you"
    ],
    "names": [
        "name", "your name", "who is this", "who am i talking to",
        "who are you", "identify yourself"
    ],
    "places": [
        "where", "place", "room", "house", "door", "window",
        "attic", "cellar", "basement", "grave", "buried"
    ],
    "time": [
        "when", "what time", "tonight", "today", "tomorrow",
        "midnight", "soon", "how long", "date", "year"
    ],
    "warning": [
        "danger", "dangerous", "safe", "scared", "afraid",
        "warn", "warning", "curse", "cursed", "bad", "evil",
        "should we be scared", "are we safe"
    ],
    "advice": [
        "help me", "advice", "guide me", "choose for me",
        "what should i do", "what do i do", "tell me what to do"
    ],
    "relationships": [
        "love", "crush", "boyfriend", "girlfriend", "partner",
        "ex", "date", "dating", "text", "miss", "relationship"
    ],
    "future": [
        "future", "fate", "destiny", "will i", "will we",
        "happen", "become", "sign", "prediction"
    ],
    "dreams": [
        "dream", "dreams", "nightmare", "sleep", "vision"
    ],
    "afterlife": [
        "afterlife", "heaven", "hell", "death", "died",
        "passed", "grave", "cemetery", "rest"
    ],
    "numbers": [
        "number", "how many", "age", "old", "count"
    ],
    "goodbye": [
        "goodbye", "bye", "end", "stop", "leave us", "depart",
        "are we done", "close"
    ],
    "food": [
        "eat", "food", "hungry", "dinner", "lunch", "breakfast",
        "snack", "cook", "restaurant", "meal", "drink", "coffee", "tea"
    ],
    "tech": [
        "python", "error", "bug", "debug", "arduino", "serial",
        "port", "raspberry", "wire", "motor", "code"
    ],
}
