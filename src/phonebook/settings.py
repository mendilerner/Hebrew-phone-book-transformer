"""Default settings. Every value can be changed per run with config["configurable"].

Example:
    graph.invoke(state, config={"configurable": {"budget_usd": 5, "tiers": {"read_page": "strong"}}})
"""

from pydantic import BaseModel, Field


class Settings(BaseModel):
    # The model ladder (decision 0007): a cheap model first, a strong one only when needed.
    # Names use the init_chat_model format "provider:model".
    models: dict[str, str] = Field(
        default_factory=lambda: {
            "cheap": "anthropic:claude-haiku-5-5",
            "strong": "anthropic:claude-sonnet-5-5",
        }
    )
    # Which ladder step each LLM node starts on. choose_fix can move a row to "strong".
    tiers: dict[str, str] = Field(
        default_factory=lambda: {
            "discover_layout": "strong",  # runs once per book, worth a good model
            "classify_page": "cheap",
            "read_page": "cheap",
            "grade_entries": "cheap",
            "choose_fix": "cheap",
            "reread_row": "cheap",
        }
    )
    budget_usd: float = 10.0  # max $ per book (decision 0007)
    max_attempts: int = 3  # retries per row
    cache_path: str = ".cache/llm.sqlite"  # dev mode: saved LLM answers


DEFAULTS = Settings()
