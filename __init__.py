"""Override the Home Assistant Assist fallback answer with a random phrase."""

from __future__ import annotations

import logging
import random
from typing import Any

import voluptuous as vol

from homeassistant.components.conversation.const import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.components.conversation.default_agent import DefaultAgent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, translation
from homeassistant.helpers.typing import ConfigType

from .const import (
    ANY_LANGUAGE,
    CONF_INCLUDE_DEFAULTS,
    CONF_RESPONSES,
    DEFAULT_TRANSLATION_LANGUAGE,
    DOMAIN,
    FALLBACK_TRANSLATION_PREFIX,
    ORIGINAL_ATTR,
    PATCH_ATTR,
)
from .helpers import parse_responses

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional(CONF_RESPONSES): vol.All(
                    cv.ensure_list,
                    [cv.string],
                    vol.Length(min=1),
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _language_candidates(language: str, default_language: str) -> list[str]:
    """Return the languages to look for phrases in, most specific first."""
    candidates: list[str] = []
    for value in (language, default_language):
        for part in (value, value.replace("_", "-").split("-")[0]):
            candidate = part.strip().lower()
            if candidate and candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _translation_values(translations: dict[str, str]) -> list[str]:
    """Collect the `fallback_N` translation keys in numeric order."""
    numbered: list[tuple[int, str]] = []
    for key, value in translations.items():
        if not key.startswith(FALLBACK_TRANSLATION_PREFIX) or not value:
            continue
        suffix = key.removeprefix(FALLBACK_TRANSLATION_PREFIX)
        if suffix.isdigit():
            numbered.append((int(suffix), value))

    return [value for _, value in sorted(numbered)]


async def async_get_default_responses(
    hass: HomeAssistant,
    language: str,
    *,
    allow_fallback: bool = True,
) -> list[str]:
    """Return the localized phrases shipped with this integration."""
    fallback_language = DEFAULT_TRANSLATION_LANGUAGE if allow_fallback else language

    for candidate in _language_candidates(language, fallback_language):
        translations = await translation.async_get_translations(
            hass,
            candidate,
            "conversation",
            [DOMAIN],
        )
        if phrases := _translation_values(translations):
            return phrases

    return []


async def async_pick_response(hass: HomeAssistant, language: str) -> str | None:
    """Return a random phrase for a language, or None to keep the default answer."""
    entry: ConfigEntry | None = hass.data.get(DOMAIN)
    if entry is None:
        return None

    settings = {**entry.data, **entry.options}
    responses = parse_responses(settings.get(CONF_RESPONSES))
    include_defaults = bool(settings.get(CONF_INCLUDE_DEFAULTS, False))
    candidates = _language_candidates(language, hass.config.language)

    # Phrases written for a matching language win over the ones without a language code.
    for candidate in candidates:
        if phrases := list(responses.get(candidate, [])):
            break
    else:
        candidate = language
        phrases = list(responses.get(ANY_LANGUAGE, []))

    if include_defaults:
        # Only phrases of the same language, to not mix languages in one answer.
        phrases += await async_get_default_responses(hass, candidate, allow_fallback=False)

    if phrases := list(dict.fromkeys(phrases)):
        return random.choice(phrases)

    # Nothing configured for this language, fall back to the phrases of the integration.
    if include_defaults or not responses:
        defaults = await async_get_default_responses(hass, language)
        if defaults:
            return random.choice(defaults)

    return None


async def _async_default_texts(hass: HomeAssistant, language: str) -> set[str]:
    """Return the answers Home Assistant would use without this integration."""
    key = f"component.{CONVERSATION_DOMAIN}.conversation.agent.done"
    texts: set[str] = set()

    for candidate in _language_candidates(language, hass.config.language):
        translations = await translation.async_get_translations(
            hass,
            candidate,
            CONVERSATION_DOMAIN,
            [CONVERSATION_DOMAIN],
        )
        if done := translations.get(key):
            texts.add(done)

    texts.add("Done")
    return texts


async def _patched_handle_trigger_result(
    self: DefaultAgent,
    result: Any,
    user_input: Any,
    chat_log: Any,
) -> str:
    """Replace the plain "Done" answer with one of the configured phrases."""
    original = getattr(DefaultAgent, ORIGINAL_ATTR)
    response_text = await original(self, result, user_input, chat_log)

    language = getattr(user_input, "language", None) or self.hass.config.language
    if response_text not in await _async_default_texts(self.hass, language):
        return response_text

    return await async_pick_response(self.hass, language) or response_text


def _install_patch() -> None:
    """Patch the default conversation agent, keeping the original method available."""
    if getattr(DefaultAgent, PATCH_ATTR, False):
        return

    setattr(DefaultAgent, ORIGINAL_ATTR, DefaultAgent._handle_trigger_result)
    DefaultAgent._handle_trigger_result = _patched_handle_trigger_result
    setattr(DefaultAgent, PATCH_ATTR, True)


@callback
def _remove_patch() -> None:
    """Restore the original conversation agent behaviour."""
    if not getattr(DefaultAgent, PATCH_ATTR, False):
        return

    original = getattr(DefaultAgent, ORIGINAL_ATTR, None)
    if original is not None:
        DefaultAgent._handle_trigger_result = original

    delattr(DefaultAgent, ORIGINAL_ATTR)
    setattr(DefaultAgent, PATCH_ATTR, False)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import a legacy configuration.yaml block into a config entry."""
    yaml_config = config.get(DOMAIN)
    if not yaml_config:
        return True

    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.warning(
            "The '%s' block in configuration.yaml is ignored, the responses are managed in "
            "the UI: remove the block from configuration.yaml",
            DOMAIN,
        )
        return True

    _LOGGER.warning(
        "The '%s' YAML configuration is deprecated: the responses were imported into "
        "Settings -> Devices & Services -> %s, remove the block from configuration.yaml",
        DOMAIN,
        DOMAIN,
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=yaml_config,
        )
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Pick up responses edited in the UI without reloading Home Assistant."""
    _LOGGER.debug("Assist fallback responses updated: %s", {**entry.data, **entry.options})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Assist Fallback Response from a config entry."""
    other = hass.data.get(DOMAIN)
    if other is not None and other is not entry:
        _LOGGER.warning("Only one '%s' config entry is supported", DOMAIN)

    _install_patch()
    hass.data[DOMAIN] = entry
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Assist fallback responses enabled: %s", {**entry.data, **entry.options})
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if hass.data.get(DOMAIN) is entry:
        hass.data.pop(DOMAIN)

    _remove_patch()
    _LOGGER.info("Assist fallback responses disabled")
    return True
