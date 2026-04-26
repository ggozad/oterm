import pytest
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.settings import ModelSettings

from oterm.providers import PROVIDER_ENV_VARS
from oterm.providers.settings import (
    PROVIDER_SETTINGS_TYPE,
    get_settings_type,
    get_supported_setting_keys,
)

COMMON_FIELDS = {"temperature", "top_p", "max_tokens", "seed"}


@pytest.mark.parametrize("provider", sorted(PROVIDER_ENV_VARS))
def test_every_known_provider_has_explicit_mapping(provider):
    assert provider in PROVIDER_SETTINGS_TYPE


@pytest.mark.parametrize("provider", sorted(PROVIDER_ENV_VARS))
def test_common_fields_supported_by_every_provider(provider):
    keys = get_supported_setting_keys(provider)
    assert COMMON_FIELDS <= keys


def test_openai_compat_resolves_to_openai_chat_settings():
    assert get_settings_type("openai-compat/lmstudio") is OpenAIChatModelSettings
    assert COMMON_FIELDS <= get_supported_setting_keys("openai-compat/lmstudio")


def test_unknown_provider_falls_back_to_base_settings():
    assert get_settings_type("nonsense") is ModelSettings
    keys = get_supported_setting_keys("nonsense")
    assert COMMON_FIELDS <= keys


def test_provider_specific_keys_are_present():
    """Provider-specific extensions show up alongside the inherited base fields."""
    anthropic_keys = get_supported_setting_keys("anthropic")
    assert "anthropic_thinking" in anthropic_keys
    assert COMMON_FIELDS <= anthropic_keys

    openai_keys = get_supported_setting_keys("openai")
    assert "openai_reasoning_effort" in openai_keys
