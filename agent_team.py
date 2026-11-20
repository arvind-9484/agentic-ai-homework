# agent_team.py  -  A role-based team of agents with hand-offs, negotiation and failure modes
from dataclasses import dataclass

# ================= COMMUNICATION PROTOCOL =================
@dataclass
class Message:
    sender: str
    receiver: str
    kind: str        # REQUEST | INFORM | REJECT | APPROVE | ESCALATE
    content: object

class Bus:
    """Shared message channel; every hand-off between agents goes through here."""
    def __init__(self, verbose=True):
        self.log, self.verbose = [], verbose
    def send(self, sender, receiver, kind, content):
        self.log.append(Message(sender, receiver, kind, content))
        if self.verbose:
            print(f"  [{sender:<10} -> {receiver:<10}] {kind:<8} {content}")

# ================= ROLE-BASED AGENTS =================
TRUE_COSTS = {"cab": 1800, "caves_entry": 25, "museum_entry": 500, "lunch": 400}
PLAUSIBLE  = {"cab": (1000, 3500), "caves_entry": (0, 200),
              "museum_entry": (0, 1000), "lunch": (100, 1500)}
BUDGET = 3000

class Researcher:
    """Specialist 1: gathers cost data (a tool call). 'mode' simulates a faulty tool."""
    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, 0
    def work(self):
        self.calls += 1
        data = dict(TRUE_COSTS)
        if self.mode == "always_wrong" or (self.mode == "wrong_once" and self.calls == 1):
            data["cab"] = 18000          # extra zero: a typical data-entry / unit error
        return data

class Writer:
    """Specialist 2: turns data into a brief. Trusts its input (as most agents do)."""
    def work(self, data):
        total = sum(data.values())
        verdict = "within budget" if total <= BUDGET else "OVER budget"
        return {"total": total,
                "text": f"Trip brief: total cost Rs {total} ({verdict} of Rs {BUDGET})."}

class Reviewer:
    """Specialist 3 (critic): independent checks. This is the error-propagation guard."""
    def check(self, data, draft):
        for item, (lo, hi) in PLAUSIBLE.items():
            if not lo <= data[item] <= hi:
                return False, f"'{item}' = {data[item]} is outside plausible range {lo}-{hi}"
        if draft["total"] != sum(data.values()):
            return False, "total does not match the sum of items"
        return True, "all checks passed"

class Planner:
    """Coordinator: assigns work, counts rounds, escalates to avoid endless loops."""
    def __init__(self, max_rounds=3):
        self.max_rounds = max_rounds

# ================= ORCHESTRATION =================
def run_crew(researcher_mode, use_reviewer, max_rounds=3, verbose=True):
    bus, planner = Bus(verbose), Planner(max_rounds)
    researcher, writer, reviewer = Researcher(researcher_mode), Writer(), Reviewer()
    bus.send("Planner", "Researcher", "REQUEST", "gather trip costs")

    for rnd in range(1, planner.max_rounds + 1):
        data = researcher.work()
        bus.send("Researcher", "Writer", "INFORM", data)
        draft = writer.work(data)
        if not use_reviewer:                           # no safety net
            bus.send("Writer", "Planner", "INFORM", draft["text"])
            return draft["total"], rnd, len(bus.log)
        bus.send("Writer", "Reviewer", "INFORM", draft["text"])
        ok, reason = reviewer.check(data, draft)
        if ok:
            bus.send("Reviewer", "Planner", "APPROVE", reason)
            return draft["total"], rnd, len(bus.log)
        bus.send("Reviewer", "Researcher", "REJECT", reason + " -> please re-check")
    bus.send("Planner", "Human", "ESCALATE", f"no agreement after {planner.max_rounds} rounds")
    return None, planner.max_rounds, len(bus.log)

# ================= EXPERIMENTS =================
CORRECT_TOTAL = sum(TRUE_COSTS.values())     # 2725

EXPERIMENTS = [
    ("1. Happy path (reviewer on)",                    "ok",           True),
    ("2. Faulty researcher, NO reviewer",              "wrong_once",   False),
    ("3. Faulty researcher, reviewer on (recovers)",   "wrong_once",   True),
    ("4. Researcher always faulty, round cap = 3",     "always_wrong", True),
]

if __name__ == "__main__":
    summary = []
    for title, mode, reviewer_on in EXPERIMENTS:
        print("=" * 72 + f"\nEXPERIMENT {title}\n" + "=" * 72)
        total, rounds, msgs = run_crew(mode, reviewer_on)
        if total is None:
            outcome = "ESCALATED to human"
        elif total == CORRECT_TOTAL:
            outcome = f"CORRECT (Rs {total})"
        else:
            outcome = f"WRONG (Rs {total}) - silent error"
        print(f"  => {outcome}\n")
        summary.append((title, rounds, msgs, outcome))

    print("=" * 72 + "\nSUMMARY\n" + "=" * 72)
    print(f"  {'Experiment':<48}{'Rounds':>7}{'Msgs':>6}  Outcome")
    for t, r, m, o in summary:
        print(f"  {t:<48}{r:>7}{m:>6}  {o}")