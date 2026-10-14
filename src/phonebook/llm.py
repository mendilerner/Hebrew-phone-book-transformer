"""Pick the model for a node (decision 0007: models come from config, not from code)."""

from langchain.chat_models import init_chat_model
from langchain_core.globals import set_llm_cache
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from phonebook.llm_cache import DiskCache
from phonebook.settings import DEFAULTS


def setting(config: RunnableConfig | None, name: str):
    """A value from config["configurable"], or the default from settings.py.

    Dict settings (models, tiers) are merged with the defaults, so a run can
    change one node without listing all of them.
    """
    configurable = (config or {}).get("configurable", {})
    default = getattr(DEFAULTS, name)
    override = configurable.get(name)
    if override is None:
        return default
    return {**default, **override} if isinstance(default, dict) else override


def model_name(node: str, config: RunnableConfig | None = None, tier: str | None = None) -> str:
    """'provider:model' for this node. `tier` ("cheap"/"strong") overrides the node's default."""
    tier = tier or setting(config, "tiers")[node]
    return setting(config, "models")[tier]


def get_model(
    node: str, config: RunnableConfig | None = None, tier: str | None = None
) -> BaseChatModel:
    return chat_model(model_name(node, config, tier))


def chat_model(name: str) -> BaseChatModel:
    """A chat model from a 'provider:model' name."""
    return init_chat_model(name)


def enable_disk_cache(path: str | None = None) -> None:
    """Turn on the dev-mode cache for all LLM calls in this process."""
    set_llm_cache(DiskCache(path or DEFAULTS.cache_path))
