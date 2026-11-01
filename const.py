"""Constants for the Assist Fallback Response integration."""

from __future__ import annotations

DOMAIN = "assist_fallback"

CONF_RESPONSES = "responses"
CONF_INCLUDE_DEFAULTS = "include_defaults"

ENTRY_TITLE = "Assist Fallback Response"

MAX_RESPONSES = 50
MAX_RESPONSE_LENGTH = 200

# Phrases in translations/<language>.json used as built-in defaults.
FALLBACK_TRANSLATION_PREFIX = f"component.{DOMAIN}.conversation.agent.fallback_"

# Key used for phrases that apply to every language.
ANY_LANGUAGE = "*"

# Fallback language for the built-in phrases.
DEFAULT_TRANSLATION_LANGUAGE = "en"

# Attributes used to keep the original conversation agent behaviour recoverable.
PATCH_ATTR = "_assist_fallback_patched"
ORIGINAL_ATTR = "_assist_fallback_original_handle_trigger_result"
