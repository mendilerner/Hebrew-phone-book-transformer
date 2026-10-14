"""Pick the model for a node (decision 0007: models come from config, not from code)."""

from langchain.chat_models import init_chat_model
from langchain_core.globals import set_llm_cache
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from phonebook.cost import cost_usd
from phonebook.images import image_block
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
    """A chat model from a 'provider:model' name.

    max_tokens: LangChain's Anthropic default is 4096. Hidden thinking also counts
    against it, so a long answer could be cut off. You pay only for tokens used.
    """
    return init_chat_model(name, max_tokens=16_000)


def enable_disk_cache(path: str | None = None) -> None:
    """Turn on the dev-mode cache for all LLM calls in this process."""
    set_llm_cache(DiskCache(path or DEFAULTS.cache_path))


def ask_structured(schema, system: str, image_paths: list[str], text: str, model: str):
    """One LLM call with images and structured output. Returns (parsed answer, cost in $).

    method="json_schema": the newest Claude models refuse forced tool calls,
    which is how LangChain's default method gets structured output (decision 0010).
    """
    llm = chat_model(model).with_structured_output(schema, method="json_schema", include_raw=True)
    content = [*map(image_block, image_paths), {"type": "text", "text": text}]
    result = llm.invoke([SystemMessage(system), HumanMessage(content=content)])
    return result["parsed"], cost_usd(result["raw"], model)
