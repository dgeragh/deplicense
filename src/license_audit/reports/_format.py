"""Shared formatting helpers for action items and incompatible license pairs.

Every renderer (terminal, markdown, CLI output) previously had its own
inline copy of these format strings. Consolidating them here keeps the
tone and structure consistent across outputs.
"""

from __future__ import annotations

from rich.markup import escape

from license_audit.core.models import ActionItem, CompatibilityResult


class ActionItemFormatter:
    """Format an ``ActionItem`` for different output targets."""

    WARNING_ICON = "\\[!]"
    ERROR_ICON = "\\[x]"
    WARNING_COLOR = "yellow"
    ERROR_COLOR = "red"

    @classmethod
    def rich(cls, item: ActionItem) -> str:
        """Rich-markup string suitable for ``console.print``."""
        icon = cls.WARNING_ICON if item.severity == "warning" else cls.ERROR_ICON
        color = cls.WARNING_COLOR if item.severity == "warning" else cls.ERROR_COLOR
        return f"  [{color}]{icon}[/{color}] {escape(item.message)}"

    @classmethod
    def markdown(cls, item: ActionItem) -> str:
        """One-line markdown bullet."""
        label = "Warning" if item.severity == "warning" else "Error"
        prefix = f"**{item.package}**: " if item.package else ""
        return f"- [{label}] {prefix}{item.message}"


class IncompatiblePairFormatter:
    """Format a ``CompatibilityResult`` pair for different output targets."""

    ICON = "\\[x]"
    COLOR = "red"

    @classmethod
    def rich(cls, pair: CompatibilityResult) -> str:
        """Rich-markup line describing the incompatible pair."""
        return (
            f"  [{cls.COLOR}]{cls.ICON}[/{cls.COLOR}] "
            f"{pair.inbound} <-> {pair.outbound}"
        )

    @classmethod
    def markdown_row(cls, pair: CompatibilityResult) -> str:
        """Single markdown table row for a compatibility matrix."""
        return f"| {pair.inbound} | {pair.outbound} | {pair.verdict.value} |"
