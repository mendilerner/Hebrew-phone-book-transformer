"""The book graph (parent). Build step 3: only the layout part so far.

    START -> load_book -> discover_layout --R--> confirm_layout (interrupt) -> END
                              ^            \\
                              |             unclear, tries left
                              +-- add_sample_page
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from phonebook.layout import (
    add_sample_page,
    confirm_layout,
    discover_layout,
    load_book,
    route_after_discover,
)
from phonebook.schema import BookState


def build_book_graph(checkpointer=None):
    graph = StateGraph(BookState)
    graph.add_node("load_book", load_book)
    graph.add_node("discover_layout", discover_layout)
    graph.add_node("add_sample_page", add_sample_page)
    graph.add_node("confirm_layout", confirm_layout)

    graph.add_edge(START, "load_book")
    graph.add_edge("load_book", "discover_layout")
    graph.add_conditional_edges("discover_layout", route_after_discover)
    graph.add_edge("add_sample_page", "discover_layout")
    graph.add_edge("confirm_layout", END)

    # interrupt() needs a checkpointer: it saves the state while the graph waits for you.
    return graph.compile(checkpointer=checkpointer or InMemorySaver())
