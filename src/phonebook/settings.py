"""Default settings. Every value can be changed per run with config["configurable"].

Example:
    graph.invoke(state, config={"configurable": {"budget_usd": 5, "tiers": {"read_claude": "strong"}}})
"""

from pydantic import BaseModel, Field


class Settings(BaseModel):
    # The model ladder (decision 0007): a cheap model first, a strong one only when needed.
    # Names use the init_chat_model format "provider:model".
    models: dict[str, str] = Field(
        default_factory=lambda: {
            "cheap": "anthropic:claude-haiku-5-5",
            "strong": "anthropic:claude-sonnet-5-5",
            "best": "anthropic:claude-opus-5-5",
            # The second reader (decision 0015). Needs OPENAI_API_KEY on your computer.
            "gpt": "openai:gpt-6-astra",
        }
    )
    # Which model each LLM node uses. The two readers must be different providers
    # (decision 0015): a name is trusted when both read it the same.
    tiers: dict[str, str] = Field(
        default_factory=lambda: {
            "discover_layout": "strong",  # runs once per book, worth a good model
            "classify_page": "cheap",
            "read_claude": "best",
            "read_gpt": "gpt",
            "tie_break": "best",  # Claude picks between the two readings
            "verify": "gpt",  # GPT confirms what the tie-breaker was sure about
        }
    )
    budget_usd: float = 10.0  # max $ per book (decision 0007)
    max_attempts: int = 3  # retries per row
    cache_path: str = ".cache/llm.sqlite"  # dev mode: saved LLM answers


DEFAULTS = Settings()
