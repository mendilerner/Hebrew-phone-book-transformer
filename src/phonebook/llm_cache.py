"""Dev mode: save every LLM answer on disk (decision 0007).

Same prompt + same model -> the saved answer comes back, and costs $0.
LangChain checks this cache before it calls the API.
"""

import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.caches import RETURN_VAL_TYPE, BaseCache
from langchain_core.load import dumps, loads
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, Generation

# Only these classes may be rebuilt from the cache file (safer than "all").
ALLOWED = [Generation, ChatGeneration, AIMessage]


class DiskCache(BaseCache):
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)")

    @staticmethod
    def _key(prompt: str, llm_string: str) -> str:
        return llm_string + "\n" + prompt

    def lookup(self, prompt: str, llm_string: str) -> RETURN_VAL_TYPE | None:
        row = self._db.execute(
            "SELECT value FROM cache WHERE key = ?", (self._key(prompt, llm_string),)
        ).fetchone()
        return loads(row[0], allowed_objects=ALLOWED) if row else None

    def update(self, prompt: str, llm_string: str, return_val: RETURN_VAL_TYPE) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?)",
            (self._key(prompt, llm_string), dumps(return_val)),
        )
        self._db.commit()

    def clear(self, **kwargs: Any) -> None:
        self._db.execute("DELETE FROM cache")
        self._db.commit()
