"""Format-specific validation rules.

Each format has a rule set registered via ``register_format_rules()``.
"""

from __future__ import annotations

from docstructure.validate.base import Rule
from docstructure.validate.rules.apa_rules import (
    ApaAbstractRule,
    ApaAuthorDateRule,
    ApaDoiRule,
    ApaFontRule,
    ApaHeadingOrderRule,
    ApaReferencesRule,
    ApaRunningHeadRule,
)
from docstructure.validate.rules.ieee_rules import (
    IeeeCitationFormatRule,
    IeeeFigureCaptionsRule,
    IeeeNumberedReferencesRule,
    IeeeSectionOrderRule,
)
from docstructure.validate.rules.mla_rules import (
    MlaAuthorPageCitationsRule,
    MlaHangingIndentRule,
    MlaHeaderRule,
    MlaNoTitlePageRule,
    MlaWorksCitedRule,
)


_FORMAT_RULES: dict[str, list[Rule]] = {}


def get_rules_for_format(format_name: str) -> list[Rule]:
    """Return all rules registered for the given format (case-insensitive)."""
    return _FORMAT_RULES.get(format_name.upper(), [])


def register_format_rules(format_name: str, rules: list[Rule]) -> None:
    """Register a list of rules for a format."""
    _FORMAT_RULES[format_name.upper()] = rules


# ── Register built-in format rule sets ──

register_format_rules("APA", [
    ApaRunningHeadRule(),
    ApaAbstractRule(),
    ApaReferencesRule(),
    ApaDoiRule(),
    ApaHeadingOrderRule(),
    ApaFontRule(),
    ApaAuthorDateRule(),
])

register_format_rules("MLA", [
    MlaNoTitlePageRule(),
    MlaHeaderRule(),
    MlaWorksCitedRule(),
    MlaAuthorPageCitationsRule(),
    MlaHangingIndentRule(),
])

register_format_rules("IEEE", [
    IeeeNumberedReferencesRule(),
    IeeeSectionOrderRule(),
    IeeeCitationFormatRule(),
    IeeeFigureCaptionsRule(),
])
