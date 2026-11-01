"""Helpers for the Assist Fallback Response integration."""

from __future__ import annotations

import re
from typing import Any

from .const import ANY_LANGUAGE, MAX_RESPONSES, MAX_RESPONSE_LENGTH

# "ru: Какая-то фраза" or "ru-RU: Какая-то фраза"
LANGUAGE_PREFIX = re.compile(r"^([A-Za-z]{2}(?:[-_][A-Za-z]{2,4})?)\s*:\s*(.*)$")


def parse_responses(raw: str | list[str] | dict[str, Any] | None) -> dict[str, list[str]]:
    """Normalize UI text, a YAML list or stored entry data into `{language: [phrases]}`."""
    if raw is None:
        return {}

    if isinstance(raw, dict):
        return {
            language: phrases
            for stored in raw.items()
            if (language := str(stored[0]).strip().lower())
            and (phrases := _clean_lines(stored[1]))
        }

    lines = raw.splitlines() if isinstance(raw, str) else list(raw)

    responses: dict[str, list[str]] = {}
    for line in lines:
        text = str(line).strip()
        if not text:
            continue

        if match := LANGUAGE_PREFIX.match(text):
            language = match.group(1).strip().lower()
            phrase = match.group(2).strip()
        else:
            language = ANY_LANGUAGE
            phrase = text

        if not phrase:
            continue

        phrases = responses.setdefault(language, [])
        if phrase not in phrases:
            phrases.append(phrase)

    return responses


def responses_to_text(responses: dict[str, list[str]]) -> str:
    """Render stored responses as lines for the multiline text field."""
    lines: list[str] = []
    for language, phrases in responses.items():
        for phrase in phrases:
            lines.append(phrase if language == ANY_LANGUAGE else f"{language}: {phrase}")
    return "\n".join(lines)


def validate_responses(responses: dict[str, list[str]]) -> str | None:
    """Return a config flow error key if the responses cannot be stored."""
    total = sum(len(phrases) for phrases in responses.values())
    if total > MAX_RESPONSES:
        return "too_many_responses"
    if any(len(phrase) > MAX_RESPONSE_LENGTH for phrases in responses.values() for phrase in phrases):
        return "response_too_long"
    return None


def _clean_lines(value: Any) -> list[str]:
    """Return stripped, non-empty and non-duplicated strings from any input."""
    if isinstance(value, str):
        value = value.splitlines()

    phrases: list[str] = []
    for item in value or []:
        phrase = str(item).strip()
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    return phrases
