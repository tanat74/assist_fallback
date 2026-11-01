"""Config flow for Assist Fallback Response."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import BooleanSelector, TextSelector, TextSelectorConfig

from .const import (
    CONF_INCLUDE_DEFAULTS,
    CONF_RESPONSES,
    DOMAIN,
    ENTRY_TITLE,
    MAX_RESPONSE_LENGTH,
    MAX_RESPONSES,
)
from .helpers import parse_responses, responses_to_text, validate_responses


def responses_schema(settings: dict[str, Any]) -> vol.Schema:
    """Return the shared form schema, prefilled with the current settings."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_RESPONSES,
                default=responses_to_text(parse_responses(settings.get(CONF_RESPONSES))),
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_INCLUDE_DEFAULTS,
                default=bool(settings.get(CONF_INCLUDE_DEFAULTS, False)),
            ): BooleanSelector(),
        }
    )


def parse_form(user_input: dict[str, Any]) -> tuple[dict[str, list[str]], bool, str | None]:
    """Validate form input, returning responses, the defaults flag and an error key."""
    responses = parse_responses(user_input.get(CONF_RESPONSES))
    include_defaults = bool(user_input.get(CONF_INCLUDE_DEFAULTS, False))

    if not responses and not include_defaults:
        return responses, include_defaults, "no_responses"

    return responses, include_defaults, validate_responses(responses)


def error_placeholders(error: str) -> dict[str, int]:
    """Return the placeholder used by the error strings."""
    return {"max": MAX_RESPONSES if error == "too_many_responses" else MAX_RESPONSE_LENGTH}


class AssistFallbackConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Assist Fallback Response."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AssistFallbackOptionsFlow:
        """Return the flow behind the "Configure" button of an entry."""
        return AssistFallbackOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow started from Settings -> Devices & Services."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=responses_schema({CONF_INCLUDE_DEFAULTS: True}),
            )

        responses, include_defaults, error = parse_form(user_input)
        if error is not None:
            return self.async_show_form(
                step_id="user",
                data_schema=responses_schema(user_input),
                errors={"base": error},
                description_placeholders=error_placeholders(error),
            )

        return self.async_create_entry(
            title=ENTRY_TITLE,
            data={CONF_RESPONSES: responses, CONF_INCLUDE_DEFAULTS: include_defaults},
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Turn the old configuration.yaml block into a config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title=ENTRY_TITLE,
            data={
                CONF_RESPONSES: parse_responses((import_data or {}).get(CONF_RESPONSES)),
                CONF_INCLUDE_DEFAULTS: False,
            },
        )


class AssistFallbackOptionsFlow(OptionsFlow):
    """Handle editing the responses of an existing config entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the phrases of the entry."""
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=responses_schema(current))

        responses, include_defaults, error = parse_form(user_input)
        if error is not None:
            return self.async_show_form(
                step_id="init",
                data_schema=responses_schema(user_input),
                errors={"base": error},
                description_placeholders=error_placeholders(error),
            )

        return self.async_create_entry(
            title="",
            data={CONF_RESPONSES: responses, CONF_INCLUDE_DEFAULTS: include_defaults},
        )
