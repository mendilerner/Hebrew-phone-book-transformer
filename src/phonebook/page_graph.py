"""The page sub-graph (decision 0015). One copy runs per page (later: started with Send).

START -> classify_page -L-> read_claude + read_gpt (parallel) -> compare_reads
compare_reads -R-> tie_break (only if they disagree) -R-> verify (only sure answers)
everything ends in finalize_page -> END. Empty and cover pages end after classify_page.
"""

from langgraph.graph import END, START, StateGraph

from phonebook.page import (
    classify_page,
    compare_reads,
    finalize_page,
    read_claude,
    read_gpt,
    route_after_classify,
    route_after_compare,
    route_after_tie_break,
    tie_break,
    verify,
)
from phonebook.schema import PageState


def build_page_graph():
    graph = StateGraph(PageState)
    graph.add_node("classify_page", classify_page)
    graph.add_node("read_claude", read_claude)
    graph.add_node("read_gpt", read_gpt)
    graph.add_node("compare_reads", compare_reads)
    graph.add_node("tie_break", tie_break)
    graph.add_node("verify", verify)
    graph.add_node("finalize_page", finalize_page)

    graph.add_edge(START, "classify_page")
    # The router returns ["read_claude", "read_gpt"]: both run in the same step (parallel).
    graph.add_conditional_edges(
        "classify_page",
        route_after_classify,
        {"read_claude": "read_claude", "read_gpt": "read_gpt", "skip": END},
    )
    # A join: compare_reads waits until BOTH readers are done.
    graph.add_edge(["read_claude", "read_gpt"], "compare_reads")
    graph.add_conditional_edges(
        "compare_reads", route_after_compare, ["tie_break", "finalize_page"]
    )
    graph.add_conditional_edges("tie_break", route_after_tie_break, ["verify", "finalize_page"])
    graph.add_edge("verify", "finalize_page")
    graph.add_edge("finalize_page", END)
    # No checkpointer here: a sub-graph uses its parent's checkpointer.
    return graph.compile()
