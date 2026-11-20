# memory_agent.py  -  Agent with short-term memory, long-term (vector) memory and tools
import ast, math, operator, re
from collections import Counter, deque

# ================= MEMORY =================
STOP = {"what", "is", "my", "the", "a", "of", "i", "am", "are", "when", "do",
        "does", "to", "for", "on", "in", "me", "you", "your", "s", "it"}

def embed(text):
    """Toy 'embedding': bag-of-words counts without stop-words.
    Swap for a real model (sentence-transformers / OpenAI) + FAISS/Chroma later."""
    return Counter(t for t in re.findall(r"[a-z0-9%]+", text.lower()) if t not in STOP)

def cosine(a, b):
    dot = sum(a[k] * b[k] for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0

class ShortTermMemory:
    """Sliding window: keeps only the last N turns (like a context window)."""
    def __init__(self, size=3):
        self.turns = deque(maxlen=size)
    def add(self, user, reply):
        self.turns.append((user, reply))
    def user_statements(self):
        return [u for u, _ in self.turns if not is_question(u)]

class LongTermMemory:
    """Mini vector store: save (text, vector); retrieve top-k by cosine similarity."""
    def __init__(self):
        self.items = []
    def save(self, text):
        self.items.append((text, embed(text)))
    def retrieve(self, query, k=1, threshold=0.1):
        q = embed(query)
        scored = sorted(((cosine(q, v), t) for t, v in self.items), reverse=True)
        return [(round(s, 2), t) for s, t in scored[:k] if s >= threshold]

# ================= TOOLS =================
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}

def run_python(expr):
    """Code-execution tool (safe arithmetic only, via AST whitelist)."""
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in OPS: return OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in OPS: return OPS[type(n.op)](ev(n.operand))
        raise ValueError("unsafe expression")
    r = ev(ast.parse(expr, mode="eval").body)
    return int(r) if float(r).is_integer() else round(r, 2)

KNOWLEDGE = {"capital of maharashtra": "Mumbai is the capital of Maharashtra.",
             "capital of india": "New Delhi is the capital of India."}

def web_search(query):
    """Mock search API. Replace with a real API (e.g. DuckDuckGo, SerpAPI) later."""
    q = embed(query)
    best = max(KNOWLEDGE, key=lambda k: cosine(q, embed(k)))
    return KNOWLEDGE[best] if cosine(q, embed(best)) > 0.5 else "No result found."

TOOLS = {"run_python": run_python, "web_search": web_search}

# ================= AGENT =================
def is_question(text):
    t = text.strip().lower()
    return t.endswith("?") or t.startswith(("calculate", "compute"))

class Agent:
    def __init__(self, name, use_stm, use_ltm, use_tools, verbose=False):
        self.name, self.use_tools, self.verbose = name, use_tools, verbose
        self.stm = ShortTermMemory(3) if use_stm else None
        self.ltm = LongTermMemory() if use_ltm else None

    def log(self, label, text):
        if self.verbose: print(f"    {label:<12}{text}")

    def recall(self, query):
        """Find a remembered fact: short-term buffer first, then vector store."""
        if self.stm:
            for s in self.stm.user_statements():
                if cosine(embed(query), embed(s)) > 0.1:
                    self.log("Memory:", f"STM hit -> {s!r}")
                    return s
        if self.ltm:
            hits = self.ltm.retrieve(query)
            if hits:
                self.log("Memory:", f"LTM hit {hits[0]}")
                return hits[0][1]
        self.log("Memory:", "nothing found")
        return None

    def call(self, tool, arg):
        self.log("Action:", f"{tool}({arg!r})")
        obs = TOOLS[tool](arg)
        self.log("Observation:", str(obs))
        return obs

    def respond(self, msg):
        text = msg.strip().rstrip("?").lower()
        text = re.sub(r"^(calculate|compute|what is)\s+", "", text)
        self.log("Thought:", f"Understand {msg!r}")

        if not is_question(msg):                      # a statement -> remember it
            if self.ltm: self.ltm.save(msg)
            return "Noted."
        if re.fullmatch(r"[\d\s+\-*/().]+", text) and self.use_tools:   # arithmetic
            return str(self.call("run_python", text))
        m = re.fullmatch(r"(\d+)% of my (\w+)", text)                    # memory + tool
        if m:
            fact = self.recall(m.group(2))
            num = re.search(r"\d+", fact) if fact else None
            if num and self.use_tools:
                return str(self.call("run_python", f"{m.group(1)}/100*{num.group()}"))
            return "I don't know."
        if "capital of" in text:                                         # search
            return self.call("web_search", text) if self.use_tools else "I don't know."
        fact = self.recall(text)                                         # plain recall
        return fact.rstrip(".") if fact else "I don't know."

    def chat(self, msg):
        reply = self.respond(msg)
        if self.stm: self.stm.add(msg, reply)
        return reply

# ================= EXPERIMENT =================
FACTS   = ["My name is Arvind.", "My exam is on 5 December.",
           "My budget is 3000 rupees.", "I prefer short answers."]
FILLERS = ["What is 2+3?", "What is 10*4?", "Hello there."]      # push facts out of STM
TESTS   = [("What is my name?",                    "Arvind",   "memory"),
           ("When is my exam?",                    "5 December", "memory"),
           ("What is 15% of my budget?",           "450",      "memory + tool"),
           ("What is the capital of Maharashtra?", "Mumbai",   "tool (search)"),
           ("Calculate 2**10 + 7",                 "1031",     "tool (code)")]

def evaluate(agent):
    for m in FACTS + FILLERS:
        agent.chat(m)
    results = []
    for q, expected, kind in TESTS:
        if agent.verbose: print(f"\n  Q: {q}")
        a = agent.chat(q)
        ok = expected.lower() in a.lower()
        if agent.verbose: print(f"  A: {a}   [{'PASS' if ok else 'FAIL'}]")
        results.append((q, kind, a, ok))
    return results

if __name__ == "__main__":
    configs = [("A: Baseline (no memory, no tools)", False, False, False),
               ("B: Short-term memory + tools",      True,  False, True),
               ("C: Short-term + long-term + tools", True,  True,  True)]
    table = []
    for name, stm, ltm, tools in configs:
        verbose = name.startswith("C")
        print("=" * 60 + f"\nAGENT {name}\n" + "=" * 60)
        res = evaluate(Agent(name, stm, ltm, tools, verbose))
        if not verbose:
            for q, kind, a, ok in res:
                print(f"  {q:<40} -> {a:<28} [{'PASS' if ok else 'FAIL'}]")
        table.append((name, sum(r[3] for r in res)))
    print("\n" + "=" * 60 + "\nSCOREBOARD\n" + "=" * 60)
    for name, score in table:
        print(f"  {name:<38} {score}/{len(TESTS)}")
