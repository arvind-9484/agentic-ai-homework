import math

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import InMemorySaver


@tool
def check_attendance_eligibility(attended: int, total: int) -> str:
    """Check if a student meets the 75% minimum attendance requirement.

    Args:
        attended: number of classes the student has attended (e.g. 28 in "28 of 40").
        total: total number of classes held (e.g. 40 in "28 of 40").
    """
    if total <= 0:
        return "Error: total classes must be greater than zero."
    if attended < 0 or attended > total:
        return "Error: attended classes must be between 0 and total classes."
    percentage = (attended / total) * 100
    if percentage >= 75:
        return f"ELIGIBLE: {percentage:.1f}% attendance."
    return f"NOT ELIGIBLE: {percentage:.1f}% attendance (below 75%)."


@tool
def classes_needed_for_eligibility(attended: int, total_so_far: int, remaining_classes: int) -> str:
    """Calculate how many of the remaining classes a student must attend to reach 75% by semester end.

    Args:
        attended: number of classes the student has attended so far (e.g. 28 in "28 of 40").
        total_so_far: total number of classes held so far, including missed ones (e.g. 40 in "28 of 40").
        remaining_classes: number of classes still to come this semester.
    """
    if total_so_far <= 0 or remaining_classes < 0:
        return "Error: total_so_far must be positive and remaining_classes cannot be negative."
    if attended < 0 or attended > total_so_far:
        return "Error: attended classes must be between 0 and total_so_far."
    final_total = total_so_far + remaining_classes
    needed_total = math.ceil(0.75 * final_total)
    more_needed = needed_total - attended
    if more_needed <= 0:
        return "You are already on track to be eligible."
    if more_needed > remaining_classes:
        best_possible = (attended + remaining_classes) / final_total * 100
        return (f"NOT POSSIBLE: even attending all {remaining_classes} remaining classes "
                f"would only reach {best_possible:.1f}%, below 75%.")
    return f"You need to attend at least {more_needed} of the remaining {remaining_classes} classes to reach 75%."


llm = ChatOllama(model="qwen2.5:3b", temperature=0)
tools = [check_attendance_eligibility, classes_needed_for_eligibility]
llm_with_tools = llm.bind_tools(tools)


def call_model(state: MessagesState):
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


builder = StateGraph(MessagesState)
builder.add_node("agent", call_model)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)


def print_trace(result):
    for msg in result["messages"]:
        name = type(msg).__name__
        if name == "AIMessage" and msg.tool_calls:
            for call in msg.tool_calls:
                print(f"AIMessage -> calls tool: {call['name']}({call['args']})")
        elif msg.content:
            print(f"{name}: {msg.content}")


if __name__ == "__main__":
    # ---- Part 1: basic memory ----
    print("=== PART 1: Basic memory ===")
    config1 = {"configurable": {"thread_id": "part1-demo"}}
    graph.invoke({"messages": [{"role": "user", "content": "I've attended 28 of 40 classes."}]}, config=config1)
    r1 = graph.invoke({"messages": [{"role": "user", "content": "Am I eligible?"}]}, config=config1)
    print_trace(r1)

    # ---- Part 2: thread isolation ----
    print("\n=== PART 2: Thread isolation ===")
    config_a = {"configurable": {"thread_id": "student-A"}}
    config_b = {"configurable": {"thread_id": "student-B"}}
    graph.invoke({"messages": [{"role": "user", "content": "I've attended 28 of 40 classes."}]}, config=config_a)
    r_b = graph.invoke({"messages": [{"role": "user", "content": "Am I eligible?"}]}, config=config_b)
    print("Thread B (should have no data to work with):")
    print_trace(r_b)
    r_a = graph.invoke({"messages": [{"role": "user", "content": "Am I eligible?"}]}, config=config_a)
    print("Thread A (should still remember):")
    print_trace(r_a)

    # ---- Part 3: multi-turn tool calling ----
    print("\n=== PART 3: Multi-turn tool calling ===")
    config3 = {"configurable": {"thread_id": "capstone-test"}}
    graph.invoke({"messages": [{"role": "user", "content": "I've attended 28 of 40 classes so far."}]}, config=config3)
    r3 = graph.invoke(
        {"messages": [{"role": "user", "content": "If 20 classes remain this semester, how many more do I need?"}]},
        config=config3,
    )
    print_trace(r3)
    print(f"\nFINAL ANSWER: {r3['messages'][-1].content}")