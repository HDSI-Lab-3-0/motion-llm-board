# openrouter/wordbanks.py
"""
Centralized word banks + keyword triggers for the Ouija board.

- WORD_BANKS: category -> list of output words/phrases (keep outputs short for spelling)
- KEYWORDS: category -> list of keyword triggers found in user question

Add categories freely:
1) Add a new entry in WORD_BANKS
2) Add a matching entry in KEYWORDS (optional but recommended)
"""

# Output tokens for YES/NO/MAYBE mode
YES_NO_MAYBE = ["YES", "NO", "MAYBE"]


# ---------------------------
# Word banks (OUTPUTS)
# ---------------------------
WORD_BANKS = {
    # --- general fallback ---
    "generic": [
        "WAIT", "TRUST", "GO", "STAY", "LISTEN", "RELAX",
        "FOCUS", "GROW", "HEAL", "PAUSE", "MOVE", "CHOOSE",
        "BREATHE", "RESET", "ALLOW", "NOTICE", "ACCEPT", "SHIFT",
    ],

    # --- actions / routines ---
    "actions": [
        "SLEEP", "REST", "WALK", "TEXT", "STUDY", "BREATHE",
        "WRITE", "CLEAN", "STRETCH", "SHOWER", "PLAN",
        "READ", "DANCE", "CREATE", "RESET", "EAT", "DRINK",
        "CALL", "LEAVE", "RETURN", "BEGIN", "FINISH",
    ],

    # --- food / drink ---
    "food": [
        "RAMEN", "PASTA", "RICE", "SOUP", "SALAD", "SUSHI", "TOAST",
        "BURRITO", "TACOS", "PIZZA", "CURRY", "NOODLES", "SANDWICH",
        "DUMPLINGS", "PHO", "BIBIMBAP", "UDON", "POKE",
        "FRUIT", "YOGURT", "COFFEE", "TEA", "SMOOTHIE",
        "BAGEL", "BOWL", "KIMCHI", "BENTO", "OMELET", "MATCHA",
    ],

    # --- relationships / dating / social ---
    "relationships": [
        "HONESTY", "BOUNDARIES", "APOLOGY", "CLOSURE",
        "PATIENCE", "LOYALTY", "SPACE", "CLARITY",
        "TRUST", "LISTEN", "RESPECT", "FORGIVE", "SOFTEN",
        "ASK", "SAYIT", "CHECKIN", "CARE", "GENTLE",
    ],

    # --- school / work / productivity ---
    "school_work": [
        "START", "REVISE", "SUBMIT", "OUTLINE",
        "PRACTICE", "EMAIL", "DEADLINE",
        "FOCUS", "PRIORITY", "DRAFT", "PLAN", "SCHEDULE",
        "BREAK", "REVIEW", "SOLVE", "SHIP", "CLEANUP",
    ],

    # --- anxiety / stress / emotional state ---
    "anxiety": [
        "BREATHE", "GROUND", "SLOW", "EASE",
        "SOFTEN", "RELEASE", "LETGO", "SAFE",
        "CALM", "STEADY", "PAUSE", "REST",
        "KIND", "OKAY", "GENTLE", "QUIET",
    ],

    # --- confidence / courage / self-worth ---
    "confidence": [
        "BRAVE", "WORTHY", "TRUSTME", "RISE",
        "SPEAK", "OWNIT", "BOLD", "SHINE",
        "PROUD", "CAPABLE", "BELIEVE", "YES",
        "MOVE", "TRY", "BEGIN", "DOIT",
    ],

    # --- health / body / recovery ---
    "health": [
        "HYDRATE", "SLEEP", "WALK", "STRETCH",
        "REST", "NOURISH", "BREATH", "CARE",
        "HEAL", "RECOVER", "BALANCE", "EASE",
        "CHECKUP", "SUNLIGHT",
    ],

    # --- fitness / movement / sports ---
    "fitness": [
        "PILATES", "YOGA", "RUN", "LIFT",
        "SURF", "HIKE", "SWIM", "CORE",
        "MOBILITY", "STRETCH", "RECOVER",
        "CARDIO", "FLOW", "TRAIN",
    ],

    # --- money / finance ---
    "money": [
        "BUDGET", "SAVE", "INVEST", "PLAN",
        "CUTBACK", "TRACK", "FOCUS", "BUILD",
        "ASK", "NEGOTIATE", "WAIT", "LEARN",
        "GROW", "SECURE",
    ],

    # --- career / decisions / future ---
    "career": [
        "APPLY", "BUILD", "PORTFOLIO", "NETWORK",
        "LEARN", "PIVOT", "COMMIT", "CHOOSE",
        "CLARITY", "FOCUS", "TRY", "EXPLORE",
        "ASK", "DRAFT", "SHIP",
    ],

    # --- creativity / art / music ---
    "creativity": [
        "CREATE", "SKETCH", "PLAY", "SING",
        "WRITE", "DRAW", "PAINT", "DESIGN",
        "JAM", "IMPROVISE", "PRACTICE", "BUILD",
        "MAKE", "DREAM",
    ],

    # --- travel / adventure ---
    "travel": [
        "GO", "BOOK", "PLAN", "EXPLORE",
        "WANDER", "ADVENTURE", "MAP", "PACK",
        "OCEAN", "MOUNTAIN", "CITY", "SUN",
        "LEAVE", "RETURN",
    ],

    # --- family / home ---
    "family": [
        "CALL", "VISIT", "LISTEN", "FORGIVE",
        "RESPECT", "PATIENT", "HOME", "CARE",
        "BOUNDARY", "KIND", "CHECKIN",
    ],

    # --- conflict / communication ---
    "communication": [
        "SPEAK", "LISTEN", "ASK", "CLARIFY",
        "REPAIR", "APOLOGIZE", "PAUSE", "RESPOND",
        "HONESTY", "BOUNDARY", "CALM", "KIND",
    ],

    # --- sleep / rest ---
    "sleep": [
        "SLEEP", "REST", "UNPLUG", "QUIET",
        "WINDDOWN", "TEA", "DARK", "CALM",
        "BREATHE", "STRETCH",
    ],

    # --- weather (one-word outputs if it ever routes here) ---
    # You can keep this minimal; ideally weather should be YES/NO/MAYBE or real lookup later.
    "weather": [
        "SUN", "CLOUD", "RAIN", "WIND", "CLEAR",
        "COOL", "WARM", "CHILL", "STORM", "FOG",
    ],

    # --- tech / coding / debugging ---
    "tech": [
        "RESTART", "UPDATE", "DEBUG", "CHECKLOG",
        "REINSTALL", "RETRY", "CONFIG", "PORT",
        "COMMIT", "PUSH", "PULL", "FIX",
    ],

    # --- luck / chance / gambling vibes ---
    "luck": [
        "MAYBE", "WAIT", "RISK", "TRY",
        "AGAIN", "LATER", "TRUST", "SHIFT",
        "ODDS", "CAREFUL",
    ],

    # --- boundaries / people-pleasing / self-advocacy ---
    "boundaries": [
        "NO", "BOUNDARY", "ASK", "PAUSE",
        "CHOOSE", "SELF", "CLARITY",
        "PROTECT", "HONOR", "TRUTH",
    ],

    # --- journaling / reflection ---
    "reflection": [
        "JOURNAL", "NOTICE", "WHY", "WRITE",
        "REFLECT", "BREATHE", "SILENCE", "TRUTH",
        "CLARITY", "LISTEN",
    ],
}


# ---------------------------
# Keyword triggers (INPUTS)
# ---------------------------
# These are substring checks against the lowercased question.
# Keep them broad and forgiving because Whisper can be messy.
KEYWORDS = {
    "food": [
        "eat", "food", "hungry", "dinner", "lunch", "breakfast", "snack", "cook", "restaurant", "meal", "drink", "coffee", "tea"
    ],
    "relationships": [
        "love", "date", "crush", "relationship", "text", "boyfriend", "girlfriend", "partner", "breakup", "miss", "talk", "ghost"
    ],
    "school_work": [
        "study", "exam", "class", "work", "job", "assignment", "homework", "project", "resume", "interview", "deadline"
    ],
    "anxiety": [
        "anxious", "anxiety", "panic", "overthink", "stressed", "stress", "worry", "scared", "cry", "sad"
    ],
    "confidence": [
        "confident", "confidence", "brave", "courage", "self worth", "insecure", "imposter", "fear"
    ],
    "health": [
        "health", "sick", "hurt", "pain", "injury", "ankle", "headache", "doctor", "hospital", "recover"
    ],
    "fitness": [
        "workout", "gym", "run", "lift", "yoga", "pilates", "surf", "hike", "cardio", "stretch"
    ],
    "money": [
        "money", "broke", "budget", "save", "spend", "rent", "pay", "salary", "credit", "debt"
    ],
    "career": [
        "career", "major", "intern", "internship", "apply", "application", "linkedin", "job", "offer"
    ],
    "creativity": [
        "creative", "draw", "art", "music", "guitar", "piano", "write", "paint", "design"
    ],
    "travel": [
        "travel", "trip", "vacation", "flight", "hotel", "beach", "nyc", "cabo", "mexico", "japan"
    ],
    "family": [
        "mom", "dad", "parents", "family", "cousin", "home", "sister", "brother"
    ],
    "communication": [
        "communicate", "conversation", "talk", "say", "tell", "message", "text", "explain", "misunderstand"
    ],
    "sleep": [
        "sleep", "tired", "insomnia", "nap", "rest", "bed", "dream"
    ],
    "weather": [
        "weather", "rain", "raining", "sunny", "cloudy", "windy", "forecast", "temperature", "temp", "storm", "fog", "cold", "hot"
    ],
    "tech": [
        "python", "error", "bug", "debug", "install", "module", "import", "raspberry", "arduino", "serial", "port", "github", "git"
    ],
    "luck": [
        "luck", "lucky", "chance", "bet", "gamble", "casino", "odds"
    ],
    "boundaries": [
        "boundary", "boundaries", "people pleaser", "guilt", "say no", "pressure", "obligated"
    ],
    "reflection": [
        "journal", "reflect", "meaning", "why", "what should i do", "what do i do", "how should i", "help me decide"
    ],
}
