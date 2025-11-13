from owlready2 import *

onto = get_ontology("travel.rdf").load()


with onto:
    class Traveler(Thing): pass
    class likesActivity(Traveler >> onto.Activity): pass
    class prefersSeason(Traveler >> onto.Season): pass
    class maxBudget(Traveler >> float): pass

    # New rule
    class Recommended(Thing): pass
    class recommends(Traveler >> onto.Destination): pass

# Create a traveler
t = onto.Traveler("Joe")
t.likesActivity.append(onto.Surfing)
t.likesActivity.append(onto.Hiking)
t.prefersSeason.append(onto.Summer)
t.prefersSeason.append(onto.Winter)
t.maxBudget.append(2000.0)

# Helper functions to check data properties
def get_data_value(ind, prop):
    vals = list(prop[ind])
    return vals[0] if vals else None

def destination_ok_for(traveler, dest):
    # activity match
    act_match = any(a in dest.offers for a in traveler.likesActivity)
    # season match
    season_match = any(s in dest.suitableIn for s in traveler.prefersSeason)
    # budget check
    cost = get_data_value(dest, onto.avgCost)
    budget = get_data_value(traveler, onto.maxBudget)
    budget_ok = (cost is not None and budget is not None and cost <= budget)
    # visa
    visa_ok = True
    if hasattr(onto, "visaFreeForCa"):
        v = get_data_value(dest, onto.visaFreeForCa)
        visa_ok = (v is None) or (v is True)
    return act_match and season_match and budget_ok and visa_ok

# Run a reasoner: recommend destinations meeting constraints
for d in onto.Destination.instances():
    if destination_ok_for(t, d):
        t.recommends.append(d)
        onto.Recommended(d.name + "_RecommendedForStudent")

# Show results
print("Recommendations:", [d.name for d in t.recommends])
