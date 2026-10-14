"""Cost of one LLM answer in dollars (decision 0007).

Each node returns {"cost_usd": cost_usd(answer, model)}. The `add` reducer on
cost_usd sums all of them up to the book.
"""

from langchain_core.messages import AIMessage

# $ per 1M tokens (input, output). Anthropic API prices, checked 2026-10-12.
# Add a line here before you use a new model (for example an OpenAI model).
PRICES: dict[str, tuple[float, float]] = {
    "anthropic:claude-opus-5-5": (4.00, 20.00),
    "anthropic:claude-sonnet-5-5": (2.00, 10.00),
    "anthropic:claude-haiku-5-5": (0.10, 0.50),
}


def cost_usd(answer: AIMessage, model: str) -> float:
    """Dollars spent on this answer. A cached answer costs 0."""
    usage = answer.usage_metadata
    if not usage:
        return 0.0
    # LangChain marks an answer that came from the cache with total_cost = 0.
    if usage.get("total_cost") == 0:
        return 0.0
    if model not in PRICES:
        raise KeyError(f"No price for {model!r}. Add it to PRICES in cost.py.")
    price_in, price_out = PRICES[model]
    # Prompt-cache reads are cheaper, but we count them at full price:
    # the budget stays on the safe side.
    return (usage["input_tokens"] * price_in + usage["output_tokens"] * price_out) / 1_000_000
