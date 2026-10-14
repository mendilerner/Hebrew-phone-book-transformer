"""The page sub-graph. One copy runs per page (later: started with Send).

START -> classify_page --L--> read_page -> finalize_page -> END
                          \\-> (empty / cover) -> END
"""

from langgraph.graph import END, START, StateGraph

from phonebook.page import classify_page, finalize_page, read_page, route_after_classify
from phonebook.schema import PageState


def build_page_graph():
    graph = StateGraph(PageState)
    graph.add_node("classify_page", classify_page)
    graph.add_node("read_page", read_page)
    graph.add_node("finalize_page", finalize_page)

    graph.add_edge(START, "classify_page")
    graph.add_conditional_edges(
        "classify_page", route_after_classify, {"read_page": "read_page", "skip": END}
    )
    graph.add_edge("read_page", "finalize_page")
    graph.add_edge("finalize_page", END)
    # No checkpointer here: a sub-graph uses its parent's checkpointer.
    return graph.compile()
