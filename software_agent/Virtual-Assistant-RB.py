import re
from datetime import datetime

#Context
class Ctx:
    def __init__(self):
        self.last_intent = None
        self.memory = {"user_name": None, "default_city": None}

    @property
    def time_of_day(self):
        h = datetime.now().hour
        if 5 <= h < 12:  return "morning"
        if 12 <= h < 17: return "afternoon"
        if 17 <= h < 22: return "evening"
        return "night"

ctx = Ctx()

# Intents
NAME_RE = r"([\w'’\-]+)"
CITY_RE = r"([\w\s'’\-]+)"

INTENTS = [
    ("greet",          re.compile(r"\b(hi|hello|hey|good\s(morning|afternoon|evening|night))\b", re.I)),
    ("help",           re.compile(r"\b(help|what\s+can\s+you\s+do|commands?)\b", re.I)),
    ("time",           re.compile(r"\b(what'?s\s+the\s+time|current\s+time|\btime\b)\b", re.I)),
    ("date",           re.compile(r"\b(what'?s\s+the\s+date|today'?s\s+date|\bdate\b)\b", re.I)),
    ("set_name",       re.compile(rf"\bmy\s+name\s+is\s+{NAME_RE}\b", re.I)),
    ("get_name",       re.compile(r"\b(what'?s\s+my\s+name|who\s+am\s+i)\b", re.I)),
    ("remember_city",  re.compile(rf"\bremember\s+my\s+city\s+is\s+{CITY_RE}\b", re.I)),
    ("weather_city",   re.compile(rf"\bweather\s+in\s+{CITY_RE}\b", re.I)),
    ("weather",        re.compile(r"\b(weather|forecast)\b", re.I)),
    ("smalltalk",      re.compile(r"\b(how\s+are\s+you|what'?s\s+up|how'?s\s+it\s+going)\b", re.I)),
    ("bye",            re.compile(r"\b(bye|goodbye|exit|quit)\b", re.I)),
]

# Handlers
def h_greet(m):
    n = ctx.memory["user_name"]
    return f"Good {ctx.time_of_day}" + (f", {n}!" if n else "!") + " How can I help you today?"

def h_help(m):
    return (
        "I can help with time, date, your name, simple weather, and small talk.\n"
        "- “what’s the time”, “what’s the date”\n"
        "- “my name is Alex” → “what’s my name”\n"
        "- “weather”, “weather in Montreal”, “remember my city is Calgary”\n"
        "- “bye” to exit"
    )

def h_time(m): return datetime.now().strftime("It's %H:%M.")
def h_date(m): return datetime.now().strftime("Today is %A, %B %d, %Y.")

def h_set_name(m):
    name = m.group(1).strip().title()
    ctx.memory["user_name"] = name
    return f"Nice to meet you, {name}! I’ll remember that."

def h_get_name(m):
    n = ctx.memory["user_name"]
    return f"You're {n}." if n else "I don't know your name yet. Say “my name is <name>”."

def h_remember_city(m):
    city = m.group(1).strip().title()
    ctx.memory["default_city"] = city
    return f"Okay, I’ll remember your city as {city}."

def _weather_stub(city):
    city = (city or ctx.memory["default_city"] or "your area").title()
    return f"(Demo) Weather in {city}: " + {"morning":"clear","afternoon":"partly cloudy","evening":"cool breeze","night":"calm"}[ctx.time_of_day] + "."

def h_weather_city(m): return _weather_stub(m.group(1).strip())
def h_weather(m):      return _weather_stub(None)
def h_smalltalk(m):    return "I'm doing well—processing intents and sipping data ☕️. What can I do for you?"
def h_bye(m):          return "Goodbye! 👋"

HANDLERS = {
    "greet": h_greet, "help": h_help, "time": h_time, "date": h_date,
    "set_name": h_set_name, "get_name": h_get_name,
    "remember_city": h_remember_city, "weather_city": h_weather_city, "weather": h_weather,
    "smalltalk": h_smalltalk, "bye": h_bye
}

# Core
def detect_intent(text):
    for tag, pat in INTENTS:
        m = pat.search(text)
        if m: return tag, m
    return "fallback", None

def respond(text):
    tag, match = detect_intent(text)
    ctx.last_intent = tag
    if tag == "fallback": return 'I’m not sure I understood. Type “help” for examples.'
    return HANDLERS[tag](match)

def repl():
    print('Assistant ready. Type “help”. “bye” to exit.')
    while True:
        try:
            user = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not user: continue
        if detect_intent(user)[0] == "bye":
            print(h_bye(None)); break
        print(respond(user))

if __name__ == "__main__":
    repl()
