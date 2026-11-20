"""
Unit 4 (CO-4): Multi-agent laptop-buying team with a supervisor.

Shared task: pick a laptop for a student: >=16 GB RAM, total cost
(price + extended warranty) within Rs 60,000.

Agents (each only touches its own tools):
  Researcher  - searches the vendor catalogs
  Analyst     - costs candidates, checks budget, negotiates with Researcher
  Reviewer    - independently verifies the Analyst's pick (can reject)
Supervisor    - routes messages, caps negotiation rounds, stops the run.

Run:  python3 agents.py            (with Reviewer)
      python3 agents.py --no-review   (Reviewer switched off)

The agents here are deterministic Python functions (no LLM call), so the run
is reproducible. Each agent exposes decide(message) so an LLM call can be
swapped in later without changing the supervisor.
"""
import statistics
import sys
from dataclasses import dataclass, field

BUDGET = 60_000
WARRANTY = 3_999
MIN_RAM = 16
MIN_CANDIDATES = 3
MAX_NEGOTIATION_ROUNDS = 2

# Two vendor feeds. Vendor A is the primary feed; vendor B is only used by
# the Reviewer. Note L5 in vendor A has a data-entry slip (5499, not 54990).
VENDOR_A = {
    "L1": ("Acer Aspire 7", 16, 57_990),
    "L2": ("Lenovo IdeaPad Slim 5", 16, 62_990),
    "L3": ("ASUS Vivobook 15", 16, 49_990),
    "L4": ("HP Pavilion 14", 8, 45_990),
    "L5": ("ASUS Zenbook 14", 16, 5_499),
    "L6": ("Dell Inspiron 15", 16, 55_990),
}
VENDOR_B = {
    "L1": 58_490, "L2": 61_990, "L3": 50_490,
    "L4": 45_990, "L5": 54_990, "L6": 56_490,
}


@dataclass
class Msg:
    sender: str
    to: str
    kind: str          # request | result | counter-request | approve | reject
    body: dict = field(default_factory=dict)


LOG = []


def send(m: Msg):
    LOG.append(m)
    print(f"[{m.sender:>10} -> {m.to:<10}] {m.kind:<15} {m.body}")
    return m


# ---------------------------------------------------------------- Researcher
class Researcher:
    """Tools: search_catalog. Never: rank, recommend, or invent specs."""

    def __init__(self):
        self.quarantined = set()

    def search_catalog(self, max_price):
        out = []
        for lid, (name, ram, price) in VENDOR_A.items():
            if lid in self.quarantined or ram < MIN_RAM or price > max_price:
                continue
            out.append({"id": lid, "name": name, "ram": ram, "price": price,
                        "source": "vendor_A"})
        return out

    def decide(self, m):
        if m.kind in ("request", "counter-request"):
            c = self.search_catalog(m.body["max_price"])
            return send(Msg("Researcher", "Analyst", "result",
                            {"max_price": m.body["max_price"], "candidates": c}))
        if m.kind == "reject":
            self.quarantined.add(m.body["item_id"])
            c = self.search_catalog(m.body["max_price"])
            return send(Msg("Researcher", "Analyst", "result",
                            {"max_price": m.body["max_price"], "candidates": c,
                             "note": f"{m.body['item_id']} quarantined"}))


# ------------------------------------------------------------------ Analyst
class Analyst:
    """Tools: compute_total, budget_check. Never: edit catalog data, or skip
    the budget check."""

    def compute_total(self, price):
        return price + WARRANTY

    def decide(self, m, round_no):
        cands = m.body["candidates"]
        viable = []
        for c in cands:
            total = self.compute_total(c["price"])
            if total <= BUDGET:
                viable.append({**c, "total": total})
        viable.sort(key=lambda c: c["total"])
        if len(viable) < MIN_CANDIDATES and round_no < MAX_NEGOTIATION_ROUNDS:
            new_cap = m.body["max_price"] + 5_000
            return send(Msg("Analyst", "Researcher", "counter-request",
                            {"reason": f"only {len(viable)} viable, need {MIN_CANDIDATES}",
                             "max_price": new_cap}))
        return send(Msg("Analyst", "Supervisor", "result",
                        {"pick": viable[0] if viable else None,
                         "shortlist": viable}))


# ----------------------------------------------------------------- Reviewer
class Reviewer:
    """Tools: second_source_price, median_check. Never: edit the pick, or
    approve without re-checking against a source the Analyst did not use."""

    def decide(self, m):
        pick, shortlist = m.body["pick"], m.body["shortlist"]
        if pick is None:
            return send(Msg("Reviewer", "Supervisor", "reject",
                            {"reason": "no pick"}))
        b_price = VENDOR_B[pick["id"]]
        diff = abs(pick["price"] - b_price) / b_price
        med = statistics.median(c["price"] for c in shortlist)
        if diff > 0.15:
            return send(Msg("Reviewer", "Researcher", "reject",
                            {"item_id": pick["id"],
                             "max_price": BUDGET - WARRANTY,
                             "reason": f"vendor A {pick['price']} vs vendor B {b_price} "
                                       f"({diff:.0%} apart)"}))
        if pick["price"] < 0.4 * med:
            return send(Msg("Reviewer", "Researcher", "reject",
                            {"item_id": pick["id"], "max_price": BUDGET - WARRANTY,
                             "reason": f"price {pick['price']} < 40% of median {med}"}))
        return send(Msg("Reviewer", "Supervisor", "approve",
                        {"item_id": pick["id"], "vendor_B_price": b_price}))


# --------------------------------------------------------------- Supervisor
def run(review=True):
    R, A, V = Researcher(), Analyst(), Reviewer()
    print(f"TASK: laptop, >= {MIN_RAM} GB RAM, total (price+warranty) <= Rs {BUDGET}\n")
    msg = send(Msg("Supervisor", "Researcher", "request", {"max_price": 50_000}))
    rounds = 0
    for _ in range(12):                      # hard step cap
        msg = R.decide(msg)                  # Researcher answers
        msg = A.decide(msg, rounds)          # Analyst evaluates
        if msg.kind == "counter-request":    # negotiation loop
            rounds += 1
            continue
        if not review:
            return msg.body["pick"]
        verdict = V.decide(msg)              # Reviewer gate
        if verdict.kind == "approve":
            return msg.body["pick"]
        msg = verdict                        # reject -> back to Researcher
        rounds = MAX_NEGOTIATION_ROUNDS      # no more widening after a reject
    return None


if __name__ == "__main__":
    review = "--no-review" not in sys.argv
    print(f"=== RUN (reviewer {'ON' if review else 'OFF'}) ===")
    pick = run(review)
    print("\nFINAL PICK:", pick)