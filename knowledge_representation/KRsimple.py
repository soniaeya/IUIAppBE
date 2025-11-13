from dataclasses import dataclass
from typing import Tuple, Dict, List


# facts
@dataclass
class Destination:
    kind: str
    activities: Tuple[str, ...]
    seasons: Tuple[str, ...]
    avg_cost: int
    avg_temp_c: int


KB: Dict[str, Destination] = {
    "Banff": Destination("Mountain", ("Hiking",), ("Summer", "Autumn"), 900, 18),
    "Lisbon": Destination("City", ("FoodTour",), ("Spring", "Autumn"), 1200, 20),
    "Cancun": Destination("Beach", ("Surfing", "FoodTour"), ("Winter", "Spring"), 1100, 27),
    "Reykjavik": Destination("City", ("Museum", "Hiking"), ("Summer",), 1400, 12),
}


@dataclass
class TravelerPref:
    likes: Tuple[str, ...]
    season: str
    max_budget: int
    dislikes_heat: bool = False
    prefers_kind: Tuple[str, ...] = ()


# rules
def rule_budget(pref: TravelerPref, dest: Destination):
    ok = dest.avg_cost <= pref.max_budget
    return ok, (f"Budget ok ({dest.avg_cost} ≤ {pref.max_budget})"
                if ok else f"Too expensive ({dest.avg_cost} > {pref.max_budget})")


def rule_season(pref: TravelerPref, dest: Destination):
    ok = pref.season in dest.seasons
    return ok, (f"Season match ({pref.season})" if ok else "Season mismatch")


def rule_activity(pref: TravelerPref, dest: Destination):
    matches = set(pref.likes) & set(dest.activities)
    ok = bool(matches)
    return ok, (f"Activity match {matches}" if ok else "No liked activities")


def rule_heat(pref: TravelerPref, dest: Destination):
    if not pref.dislikes_heat:
        return True, "Heat tolerance irrelevant"
    ok = dest.avg_temp_c <= 24
    return ok, (f"Not too hot ({dest.avg_temp_c}°C)" if ok else f"Too hot ({dest.avg_temp_c}°C)")


def rule_kind(pref: TravelerPref, dest: Destination):
    if not pref.prefers_kind:
        return True, "No kind preference"
    ok = dest.kind in pref.prefers_kind
    return ok, (f"Preferred kind ({dest.kind})" if ok else f"Not preferred kind ({dest.kind})")


RULES: List = [rule_budget, rule_season, rule_activity, rule_heat, rule_kind]


# evaluating rules
def evaluate(pref: TravelerPref, kb: Dict[str, Destination]):
    scored = []
    for name, dest in kb.items():
        explanations = []
        passed = 0
        for rule in RULES:
            ok, why = rule(pref, dest)
            explanations.append(("PASS" if ok else "FAIL", why))
            if ok:
                passed += 1
        score = passed / len(RULES)
        scored.append((score, name, explanations))
    return sorted(scored, reverse=True)


# Runner
prefs = TravelerPref(
    likes=("Hiking",),
    season="Summer",
    max_budget=1000,
    dislikes_heat=True,
    prefers_kind=("Mountain",)
)

# results = evaluate(prefs, KB)
# for score, name, expl in results:
#     print(f"\n{name}: score={score:.2f}")
#     for status, why in expl:
#         print(" -", status, "|", why)

print(KB)