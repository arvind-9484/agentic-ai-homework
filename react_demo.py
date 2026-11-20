# react_demo.py  -  Live demo for group critique: a FLAWED ReAct agent vs an IMPROVED one
# Goal: "Book the cheapest transport from Pune to Lonavala for tomorrow, budget Rs 500."

WORLD = {
    "cab":        {"cost": 1800, "available": True},
    "bus":        {"cost": 250,  "available": False, "why": "sold out"},
    "train":      {"cost": 90,   "available": False, "why": "cancelled for maintenance"},
    "shared_cab": {"cost": 400,  "available": True},
}
BUDGET = 500

# ---------- Tools (the agent's Actions) ----------
def search_options(_):
    return {m: v["cost"] for m, v in WORLD.items()}

def check_availability(mode):
    v = WORLD[mode]
    return "available" if v["available"] else f"unavailable ({v['why']})"

def book(mode):
    v = WORLD[mode]
    return f"CONFIRMED BK-1042: {mode} for Rs {v['cost']}" if v["available"] else f"ERROR: {mode} {v['why']}"

TOOLS = {"search_options": search_options, "check_availability": check_availability, "book": book}

class Trace:
    """Prints each Thought / Action / Observation and records them for scoring."""
    def __init__(self):
        self.steps, self.n = [], 0
    def step(self, thought, tool, arg):
        self.n += 1
        print(f"Step {self.n}")
        print(f"  Thought:     {thought}")
        print(f"  Action:      {tool}({arg!r})")
        obs = TOOLS[tool](arg)
        print(f"  Observation: {obs}\n")
        self.steps.append((tool, arg, obs))
        return obs

# ---------- Agent 1: FLAWED (for the group to critique) ----------
def flawed_agent(max_steps=4):
    print("=" * 70 + "\nAGENT 1 (flawed)\n" + "=" * 70)
    t = Trace()
    options = t.step("I need the list of transport options.", "search_options", None)
    cheapest = min(options, key=options.get)
    last = ""
    while t.n < max_steps:
        thought = (f"The cheapest option is {cheapest}. Book it now." if not last.startswith("ERROR")
                   else "The booking did not go through. Try booking again.")
        last = t.step(thought, "book", cheapest)
    claim = f"Done! Booked {cheapest} for Rs {options[cheapest]}."
    print(f"FINAL ANSWER (claimed): {claim}\n")
    return t, claim

# ---------- Agent 2: IMPROVED (the group's proposed fix) ----------
def improved_agent(budget=BUDGET):
    print("=" * 70 + "\nAGENT 2 (improved)\n" + "=" * 70)
    t = Trace()
    options = t.step("I need the list of transport options.", "search_options", None)
    candidates = sorted((c, m) for m, c in options.items() if c <= budget)       # utility: cost, within budget
    print(f"  [PLAN] Options within Rs {budget}, cheapest first: {[m for _, m in candidates]}\n")
    failed, claim = set(), None
    for cost, mode in candidates:
        status = t.step(f"Check {mode} (Rs {cost}) BEFORE booking.", "check_availability", mode)
        if status != "available":
            failed.add(mode)
            print(f"  [REPLAN] Assumption '{mode} is bookable' violated. Failed so far: {sorted(failed)}. Trying next option.\n")
            continue
        result = t.step(f"{mode} is available. Book it.", "book", mode)
        if result.startswith("CONFIRMED"):
            claim = f"Booked {mode} for Rs {cost}. Confirmation: {result.split()[1].rstrip(':')}"
            break
    if claim is None:
        claim = "No option within budget could be booked. Escalating to the user."
    print(f"FINAL ANSWER: {claim}\n")
    return t, claim

# ---------- Scorecard: the criteria the group should use ----------
def score(name, t, claim):
    actions = [(a, b) for a, b, _ in t.steps]
    repeated_fail = sum(1 for i, (a, b, o) in enumerate(t.steps) if str(o).startswith("ERROR") and (a, b) in actions[:i])
    checked = any(a == "check_availability" for a, _, _ in t.steps)
    supported = any(str(o).startswith("CONFIRMED") for _, _, o in t.steps)
    claimed_success = claim.startswith(("Done", "Booked"))
    return [name, "Yes" if checked else "No", repeated_fail,
            "Yes" if (not claimed_success or supported) else "NO (hallucinated success)",
            len(t.steps)]

if __name__ == "__main__":
    t1, c1 = flawed_agent()
    t2, c2 = improved_agent()
    rows = [score("Agent 1 (flawed)", t1, c1), score("Agent 2 (improved)", t2, c2)]
    print("=" * 70 + "\nCRITIQUE SCORECARD\n" + "=" * 70)
    print(f"  {'Agent':<20}{'Checked first?':<16}{'Repeated fails':<16}{'Claim supported?':<28}Steps")
    for r in rows:
        print(f"  {r[0]:<20}{r[1]:<16}{r[2]:<16}{r[3]:<28}{r[4]}")