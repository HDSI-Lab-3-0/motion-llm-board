# openrouter/wordbanks.py
"""
Centralized word banks for the Ouija board.
Add words here without touching pi_runner logic.

All words should be short-ish and UPPERCASE because the board spells them.
"""

YES_NO_MAYBE = ["YES", "NO", "MAYBE"]

# -----------------------------
# FOOD (NO DRINKS IN HERE)
# -----------------------------
FOOD_WORDS = [
    "RAMEN", "PASTA", "RICE", "SOUP", "SALAD", "SUSHI", "TOAST",
    "BURRITO", "TACOS", "PIZZA", "CURRY", "NOODLES", "SANDWICH",
    "DUMPLINGS", "PHO", "BIBIMBAP", "UDON", "POKE", "BENTO",
    "BAGEL", "OMELET", "PANCAKES", "WAFFLES", "AVOCADO",
    "KIMCHI", "FRIEDRICE", "STIRFRY", "BULGOGI", "KATSU",
    "SHAKSHUKA", "RISOTTO", "GNOCCHI", "LASAGNA", "TORTELLINI",
    "BURGER", "FRIES", "NUGGETS", "WINGS", "STEAK",
    "SALMON", "TUNA", "SHRIMP", "LOBSTER", "CRAB",
    "SAMOSA", "BIRYANI", "TIKKA", "DAL", "NAAN",
    "PAELLA", "TAPAS", "GYRO", "FALAFEL", "HUMMUS",
    "KBBQ", "HOTDOG", "CHILI", "BBQ", "QUESADILLA",
    "NACHOS", "ENCHILADA", "TAMAL", "POZOLE",
    "FRUIT", "YOGURT", "GRANOLA", "OATMEAL",
    "ICECREAM", "COOKIE", "BROWNIE", "DONUT"
]

# -----------------------------
# DRINKS
# -----------------------------
DRINK_WORDS = [
    "WATER", "MATCHA", "COFFEE", "TEA", "LATTE",
    "JUICE", "SMOOTHIE", "BOBA", "SODA",
    "LEMONADE", "ICETEA", "ESPRESSO", "CAPPUCCINO",
    "MOCHA", "CHAI", "MILK", "COCONUT", "SPARKLING"
]

# -----------------------------
# ACTION / GENERAL
# -----------------------------
ACTION_WORDS = [
    "SLEEP", "REST", "WALK", "TEXT", "STUDY", "BREATHE",
    "WRITE", "CLEAN", "STRETCH", "SHOWER", "PLAN",
    "READ", "DANCE", "CREATE", "RESET", "CALL",
    "EAT", "DRINK", "JOURNAL", "MEDITATE", "MOVE",
    "RUN", "HIKE", "COOK", "ORGANIZE", "FINISH",
    "BEGIN", "RETURN", "LEAVE", "PAUSE", "LISTEN"
]

GENERIC_WORDS = [
    "WAIT", "TRUST", "GO", "STAY", "LISTEN", "RELAX",
    "FOCUS", "GROW", "HEAL", "PAUSE", "MOVE", "CHOOSE",
    "ALLOW", "NOTICE", "SHIFT", "ACCEPT", "SOFTEN",
    "BOLD", "CALM", "STEADY", "QUIET", "START"
]

# -----------------------------
# RELATIONSHIPS / SOCIAL
# -----------------------------
RELATIONSHIP_WORDS = [
    "HONESTY", "BOUNDARIES", "APOLOGY", "CLOSURE",
    "PATIENCE", "LOYALTY", "SPACE", "CLARITY",
    "TRUST", "RESPECT", "LISTEN", "GENTLE",
    "CHECKIN", "COMMUNICATE", "ASK", "FORGIVE",
    "HEART", "CARE", "TRUTH", "SOFTEN"
]

COMMUNICATION_WORDS = [
    "CLARIFY", "ASK", "LISTEN", "SPEAK",
    "PAUSE", "REPAIR", "HONESTY", "KIND",
    "CHECKIN", "RESPOND", "EXPLAIN", "TRUTH"
]

FAMILY_WORDS = [
    "CALL", "VISIT", "LISTEN", "PATIENT",
    "KIND", "HOME", "RESPECT", "BOUNDARY",
    "FORGIVE", "CARE", "CHECKIN"
]

BOUNDARY_WORDS = [
    "NO", "BOUNDARY", "PROTECT", "CLARITY",
    "TRUTH", "CHOOSE", "SELF", "PAUSE",
    "ASK", "HONOR", "RESPECT"
]

# -----------------------------
# SCHOOL / WORK / PRODUCTIVITY
# -----------------------------
SCHOOL_WORK_WORDS = [
    "START", "REVISE", "SUBMIT", "OUTLINE",
    "PRACTICE", "EMAIL", "DEADLINE",
    "DRAFT", "FOCUS", "PLAN", "SCHEDULE",
    "REVIEW", "SOLVE", "BUILD", "SHIP",
    "CLEANUP", "PRIORITY", "ORGANIZE"
]

CAREER_WORDS = [
    "APPLY", "NETWORK", "PORTFOLIO", "INTERVIEW",
    "BUILD", "PIVOT", "LEARN", "CHOOSE",
    "CLARITY", "FOCUS", "TRY", "EXPLORE",
    "DRAFT", "SHIP", "ASK", "FOLLOWUP"
]

TECH_WORDS = [
    "RESTART", "UPDATE", "DEBUG", "CHECKLOG",
    "RETRY", "CONFIG", "PORT", "SERIAL",
    "INSTALL", "IMPORT", "FIX", "PUSH",
    "PULL", "COMMIT", "BRANCH", "MERGE"
]

# -----------------------------
# MENTAL / EMOTIONAL
# -----------------------------
ANXIETY_WORDS = [
    "BREATHE", "GROUND", "SLOW", "EASE",
    "SOFTEN", "RELEASE", "LETGO", "SAFE",
    "CALM", "STEADY", "PAUSE", "REST",
    "KIND", "OKAY", "QUIET", "GENTLE"
]

CONFIDENCE_WORDS = [
    "BRAVE", "WORTHY", "BELIEVE", "RISE",
    "SPEAK", "OWNIT", "BOLD", "SHINE",
    "PROUD", "CAPABLE", "YES", "DOIT",
    "TRY", "BEGIN", "MOVE", "TRUSTME"
]

REFLECTION_WORDS = [
    "JOURNAL", "REFLECT", "NOTICE", "WHY",
    "TRUTH", "CLARITY", "SILENCE", "LISTEN",
    "MEANING", "LESSON", "SHIFT", "ACCEPT"
]

LUCK_WORDS = [
    "MAYBE", "WAIT", "TRY", "AGAIN",
    "LATER", "RISK", "CAREFUL", "ODDS",
    "TRUST", "SHIFT"
]

# -----------------------------
# HEALTH / FITNESS / LIFE
# -----------------------------
HEALTH_WORDS = [
    "HYDRATE", "SLEEP", "REST", "STRETCH",
    "NOURISH", "SUNLIGHT", "BREATHE", "CARE",
    "HEAL", "RECOVER", "BALANCE", "EASE"
]

FITNESS_WORDS = [
    "YOGA", "PILATES", "HIKE", "RUN",
    "SURF", "SWIM", "LIFT", "CORE",
    "FLOW", "MOBILITY", "TRAIN", "MOVE"
]

MONEY_WORDS = [
    "BUDGET", "SAVE", "TRACK", "PLAN",
    "BUILD", "SECURE", "CUTBACK", "LEARN",
    "GROW", "WAIT", "FOCUS", "NEGOTIATE"
]

TRAVEL_WORDS = [
    "GO", "BOOK", "PLAN", "PACK",
    "EXPLORE", "WANDER", "ADVENTURE",
    "OCEAN", "MOUNTAIN", "CITY", "SUN"
]

CREATIVITY_WORDS = [
    "CREATE", "SKETCH", "WRITE", "DRAW",
    "PAINT", "DESIGN", "PLAY", "JAM",
    "IMPROVISE", "MAKE", "DREAM", "BUILD"
]

SLEEP_WORDS = [
    "SLEEP", "REST", "UNPLUG", "WINDDOWN",
    "QUIET", "TEA", "DARK", "CALM",
    "BREATHE", "STRETCH"
]
