"""Debug mode (--debug): see every message sent to the LLM and every step of the graph.

Two LangChain / LangGraph ideas are used here:
- A callback handler: LangChain calls it before and after every LLM call. The graph
  passes it down to the nodes by itself (through `config["callbacks"]`).
- graph.stream(): runs the graph like invoke(), but yields after every step, so we
  can print what each node returned (stream_mode="updates").
"""

import json
import sys
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

LINE = "=" * 80


def _out(text: str) -> None:
    print(text, file=sys.stderr)  # stderr: debug text does not mix with the normal output


def _json(value: Any) -> str:
    def default(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        return repr(obj)

    plain = json.loads(json.dumps(value, default=default))  # objects -> dicts and lists
    return json.dumps(_hide_images(plain), ensure_ascii=False, indent=2)


def _hide_images(value: Any) -> Any:
    """An image is a very long base64 text. Show its size instead.

    LangChain may turn our image block into another format before the callback
    sees it (for example an "image_url" with a "data:..." URL), so we look at
    every text value, not at one format.
    """
    if isinstance(value, list):
        return [_hide_images(v) for v in value]
    if isinstance(value, dict):
        return {k: _hide_images(v) for k, v in value.items()}
    if isinstance(value, str) and len(value) > 300 and " " not in value:
        return f"<image data, {len(value)} chars>"
    return value


def format_message(message: BaseMessage) -> str:
    content = _hide_images(message.content)
    text = content if isinstance(content, str) else _json(content)
    return f"--- {message.type} ---\n{text}"


class LLMPrinter(BaseCallbackHandler):
    """Prints the full prompt before each LLM call and the full answer after it."""

    def on_chat_model_start(self, serialized, messages: list[list[BaseMessage]], **kwargs) -> None:
        params = kwargs.get("invocation_params") or {}
        metadata = kwargs.get("metadata") or {}
        model = params.get("model") or metadata.get("ls_model_name") or "?"
        _out(f"\n{LINE}\nLLM CALL  model={model}\n{LINE}")
        for message in messages[0]:
            _out(format_message(message))

    def on_llm_end(self, response, **kwargs) -> None:
        generation = response.generations[0][0]
        message = getattr(generation, "message", None)
        _out(f"{LINE}\nLLM ANSWER\n{LINE}")
        _out(format_message(message) if message else generation.text)
        if message is not None and getattr(message, "usage_metadata", None):
            _out(f"usage: {_json(message.usage_metadata)}")


def run_graph(graph, graph_input, config: dict, debug: bool) -> dict:
    """Like graph.invoke(), but in debug mode prints every node's update and the LLM calls."""
    if not debug:
        return graph.invoke(graph_input, config)

    config = {**config, "callbacks": [*config.get("callbacks", []), LLMPrinter()]}
    state: dict = {}
    step = 0
    # subgraphs=True: also show the steps of graphs that run inside a node
    # (the read_page agent is a graph too). `namespace` says which graph it is.
    stream = graph.stream(graph_input, config, stream_mode=["updates", "values"], subgraphs=True)
    for namespace, mode, chunk in stream:
        inside = " > ".join(n.split(":")[0] for n in namespace)
        if mode == "values":
            if not namespace:
                state = chunk  # the full state of the main graph after this step
            continue
        for node, update in chunk.items():  # mode == "updates": what each node returned
            if node == "__interrupt__":
                _out(f"\n{LINE}\nINTERRUPT (the graph pauses and waits for a human)\n{LINE}")
                _out(_json([i.value for i in update]))
                state = {**state, "__interrupt__": update}
                continue
            step += 1
            where = f"{inside} > {node}" if inside else node
            _out(f"\n{LINE}\nSTEP {step}: {where} returned\n{LINE}\n{_json(update)}")
    return state
