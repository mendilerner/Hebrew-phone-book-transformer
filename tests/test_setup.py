from langchain_core.globals import set_llm_cache
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from phonebook.cost import cost_usd
from phonebook.llm import model_name
from phonebook.llm_cache import DiskCache

USAGE = {"input_tokens": 2_000, "output_tokens": 1_000, "total_tokens": 3_000}


def test_cost_from_tokens():
    answer = AIMessage("x", usage_metadata=USAGE)
    # Sonnet 5.5: 2000 * $2/1M + 1000 * $10/1M = $0.014
    assert round(cost_usd(answer, "anthropic:claude-sonnet-5-5"), 6) == 0.014


def test_unknown_model_fails_loudly():
    answer = AIMessage("x", usage_metadata=USAGE)
    try:
        cost_usd(answer, "openai:some-model")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_model_ladder_and_config_override():
    assert model_name("read_page") == "anthropic:claude-haiku-5-5"
    assert model_name("read_page", tier="strong") == "anthropic:claude-sonnet-5-5"
    config = {"configurable": {"tiers": {"read_page": "strong"}}}
    assert model_name("read_page", config) == "anthropic:claude-sonnet-5-5"
    # other nodes keep their defaults (the override is merged, not a replacement)
    assert model_name("classify_page", config) == "anthropic:claude-haiku-5-5"


def test_disk_cache_answer_is_free(tmp_path):
    set_llm_cache(DiskCache(tmp_path / "llm.sqlite"))
    try:
        answers = iter([AIMessage("first", usage_metadata=USAGE), AIMessage("second")])
        model = GenericFakeChatModel(messages=answers)
        first = model.invoke("read this page")
        again = model.invoke("read this page")  # same prompt -> from the cache
        assert again.content == "first"
        assert cost_usd(first, "anthropic:claude-haiku-5-5") > 0
        assert cost_usd(again, "anthropic:claude-haiku-5-5") == 0
    finally:
        set_llm_cache(None)
