# react_planner.py
WORLD = {"weather": "rain"}   # try "sunny" to see the no-replan path

# ---------- Tools (the agent's "Actions") ----------
def check_weather(city):
    return WORLD["weather"]

def find_places(kind):
    catalog = {"outdoor": ["Tiger Point", "Bhushi Dam"],
               "indoor":  ["Karla Caves", "Wax Museum"]}
    return catalog[kind]

def book_cab(dest):
    return f"Cab booked to {dest}"

def check_budget(mode):
    cost = {"outdoor": 2200, "indoor": 2800}[mode]
    return {"cost": cost, "ok": cost <= 3000}

TOOLS = {"check_weather": check_weather, "find_places": find_places,
         "book_cab": book_cab, "check_budget": check_budget}

# ---------- Stub "reasoner": swap with an LLM call later ----------
def reason(task, ctx):
    if task == "weather":
        return ("I assumed sunny weather. Verify before choosing places.",
                ("check_weather", "Lonavala"))
    if task == "places":
        return (f"Weather is {ctx['weather']}, so choose {ctx['mode']} places.",
                ("find_places", ctx["mode"]))
    if task == "budget":
        return (f"Check that the {ctx['mode']} plan fits the ₹3,000 budget.",
                ("check_budget", ctx["mode"]))
    if task == "transport":
        return ("Book transport to the first chosen place.",
                ("book_cab", ctx["places"][0]))
    return ("All sub-tasks done; summarise.", None)

# ---------- Assumption check -> triggers replanning ----------
def violated(task, obs, ctx):
    return task == "weather" and obs != ctx["assumed_weather"]

def replan(remaining, ctx):
    ctx["mode"] = "indoor"
    new_plan = ["places", "budget", "transport", "summary"]
    print(f"  [REPLAN] Assumption 'sunny' violated.")
    print(f"           Old remaining plan: {remaining}")
    print(f"           New plan:           {new_plan}\n")
    return new_plan

# ---------- The ReAct loop ----------
def run(goal, max_steps=10):
    ctx = {"assumed_weather": "sunny", "mode": "outdoor"}
    plan = ["weather", "places", "transport", "summary"]
    print(f"GOAL: {goal}\nINITIAL PLAN: {plan}\n")

    for step in range(1, max_steps + 1):
        if not plan:
            break
        task = plan.pop(0)
        thought, action = reason(task, ctx)
        print(f"Step {step} | Task: {task}")
        print(f"  Thought:     {thought}")
        if action is None:
            print(f"  Final:       {ctx.get('places')} via {ctx.get('booking')}, mode={ctx['mode']}")
            break
        tool, arg = action
        print(f"  Action:      {tool}({arg!r})")
        obs = TOOLS[tool](arg)
        print(f"  Observation: {obs}")

        # store results
        if task == "weather":   ctx["weather"] = obs
        if task == "places":    ctx["places"] = obs
        if task == "transport": ctx["booking"] = obs

        if violated(task, obs, ctx):
            plan = replan(plan, ctx)
        if task == "budget" and not obs["ok"]:
            print("  [REPLAN] Over budget; cheaper option needed.")
            break
        print()

run("Plan a one-day trip from Pune to Lonavala under ₹3,000")
