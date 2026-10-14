"""Debug mode (--debug): see every step of the graph and every message sent to the LLM.

Two places get the output:
- The terminal shows a short TREE: each node of the main graph, and indented under
  it the steps of a graph that runs inside that node (the read_page agent).
- A UTF-8 file gets the same tree plus every detail: full prompts, full answers,
  and everything each node returned.

LangChain / LangGraph ideas used here:
- A callback handler: LangChain calls it before and after every LLM call. It reaches
  LLM calls inside nodes by itself (config is passed down through the run).
- graph.stream(stream_mode="tasks", subgraphs=True): yields when a node starts and
  when it ends, also for graphs that run inside a node. `namespace` says which graph.
"""

import json
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel

from phonebook.cost import PRICES, cost_usd

LINE = "=" * 80
INDENT = "    "


def _plain(value: Any) -> Any:
    def default(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        return repr(obj)

    return _hide_images(json.loads(json.dumps(value, default=default)))


def _json(value: Any) -> str:
    return json.dumps(_plain(value), ensure_ascii=False, indent=2)


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


def _short(text: str, size: int = 70) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= size else text[: size - 3] + "..."


def describe_message(message: BaseMessage) -> str:
    """One line: what this message is, in agent terms."""
    if isinstance(message, AIMessage):
        if message.tool_calls:
            calls = ", ".join(
                f"{c['name']}({', '.join(f'{k}={v}' for k, v in c['args'].items())})"
                for c in message.tool_calls
            )
            return f"model asks for tools: {calls}"
        return "model gives its final answer (no tool calls)"
    if isinstance(message, ToolMessage):
        parts = message.content if isinstance(message.content, list) else [message.content]
        images = sum(isinstance(p, dict) and p.get("type") == "image" for p in parts)
        what = f"{images} image(s)" if images else _short(message.content, 50)
        return f"tool result for {message.name or 'tool'}: {what}"
    if isinstance(message, HumanMessage):
        return f'note to the model: "{_short(message.content)}"'
    return f"{message.type} message"


def summarize(result: Any) -> str:
    """One line about what a node returned."""
    if result is None:
        return "nothing changed"
    if not isinstance(result, dict):
        return _short(repr(result))
    parts = []
    for key, value in result.items():
        if key == "messages":
            parts.extend(describe_message(m) for m in value if isinstance(m, BaseMessage))
        elif key == "jump_to":
            parts.append(f"jump to {value}")
        elif key == "structured_response":
            if hasattr(value, "entries"):
                parts.append(f"structured answer: {len(value.entries)} entries")
        elif isinstance(value, list):
            parts.append(f"{key}: {len(value)} item(s)")
        elif isinstance(value, float):
            parts.append(f"{key}: {value:.4f}")
        elif isinstance(value, (str, int, bool)) or value is None:
            parts.append(f"{key}: {_short(value, 40)}")
        elif isinstance(value, dict):
            parts.append(f"{key}: {_short(json.dumps(_plain(value), ensure_ascii=False), 40)}")
        else:
            parts.append(f"{key}: {type(value).__name__}")
    return "; ".join(parts) or "nothing changed"


class DebugLog:
    """Writes the tree to the terminal and the file, and details only to the file."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.file = path.open("a", encoding="utf-8")  # UTF-8: Hebrew stays readable
        self.depth = 0
        self.pending: dict[str, list[str]] = {}  # task id -> LLM lines, shown when it ends

    def tree(self, text: str, depth: int | None = None) -> None:
        line = INDENT * (self.depth if depth is None else depth) + text
        print(line)
        self.file.write(line + "\n")

    def detail(self, title: str, body: str) -> None:
        self.file.write(f"{LINE}\n{title}\n{LINE}\n{body}\n\n")

    def close(self) -> None:
        self.file.close()


class LLMPrinter(BaseCallbackHandler):
    """Before each LLM call: the full prompt (file). After it: tokens and cost (tree)."""

    def __init__(self, log: DebugLog):
        self.log = log

    def on_chat_model_start(self, serialized, messages: list[list[BaseMessage]], **kwargs):
        params = kwargs.get("invocation_params") or {}
        metadata = kwargs.get("metadata") or {}
        self.model = params.get("model") or metadata.get("ls_model_name") or "?"
        # Which node run (task) made this call: the last part of its checkpoint namespace.
        namespace = metadata.get("langgraph_checkpoint_ns") or metadata.get("checkpoint_ns") or ""
        self.task_id = namespace.split("|")[-1].split(":")[-1]
        body = "\n".join(format_message(m) for m in messages[0])
        self.log.detail(f"LLM CALL  model={self.model}  (full prompt)", body)

    def on_llm_end(self, response, **kwargs):
        generation = response.generations[0][0]
        message = getattr(generation, "message", None)
        self.log.detail("LLM ANSWER", format_message(message) if message else generation.text)
        usage = getattr(message, "usage_metadata", None) or {}
        name = f"anthropic:{self.model}"
        price = f", ${cost_usd(message, name):.4f}" if name in PRICES and usage else ""
        tokens = f"{usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out"
        cached = " (from cache, $0)" if usage.get("total_cost") == 0 else ""
        # Not printed now: the stream shows steps a bit later than they run, so the
        # line is printed when its node ends, under that node.
        line = f"LLM call {self.model}: {tokens} tokens{price}{cached}"
        self.log.pending.setdefault(self.task_id, []).append(line)


def _where(namespace: tuple[str, ...]) -> str:
    return " > ".join(n.split(":")[0] for n in namespace)


def run_graph(graph, graph_input, config: dict, debug: Path | str | bool | None) -> dict:
    """Like graph.invoke(). With `debug` (a file path, or True for output/debug.txt),
    print the tree of steps and write all details to that file."""
    if not debug:
        return graph.invoke(graph_input, config)

    log = DebugLog(Path("output/debug.txt") if debug is True else Path(debug))
    log.detail(
        "THE GRAPH (Mermaid, paste into https://mermaid.live)", graph.get_graph().draw_mermaid()
    )
    config = {**config, "callbacks": [*config.get("callbacks", []), LLMPrinter(log)]}
    state: dict = {}
    stream = graph.stream(
        graph_input, config, stream_mode=["tasks", "updates", "values"], subgraphs=True
    )
    try:
        for namespace, mode, chunk in stream:
            depth = len(namespace)
            if mode == "values":
                if not namespace:
                    state = chunk  # the full state of the main graph after this step
            elif mode == "updates":
                if not namespace and "__interrupt__" in chunk:
                    state = {**state, "__interrupt__": chunk["__interrupt__"]}
            elif "input" in chunk:  # a task (one node run) starts
                log.depth = depth
                name = chunk["name"]
                if depth == 0:
                    log.tree(f"STEP {name}", 0)
                else:
                    kind = " (middleware)" if "." in name else ""
                    log.tree(f"{_where(namespace)} agent > {name}{kind}", depth)
            else:  # the task ended
                for line in log.pending.pop(chunk["id"], []):
                    log.tree(INDENT + line, depth)
                where = _where(namespace) + " > " if namespace else ""
                log.detail(f"{where}{chunk['name']} RETURNED", _json(chunk.get("result")))
                if chunk.get("interrupts"):
                    log.tree(f"{INDENT}-> PAUSED: waiting for a human answer", depth)
                    log.detail("INTERRUPT (the question)", _json(chunk["interrupts"]))
                else:
                    log.tree(f"{INDENT}-> {summarize(chunk.get('result'))}", depth)
    finally:
        for lines in log.pending.values():  # calls we could not match to a step
            for line in lines:
                log.tree(INDENT + line, 0)
        log.tree(f"(all details: {log.path})", 0)
        log.close()
    return state
