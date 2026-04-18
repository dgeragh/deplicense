"""Shared formatters for action items and incompatible license pairs."""

from __future__ import annotations

from rich.markup import escape

from license_audit.core.models import ActionItem, CompatibilityResult


class ActionItemFormatter:
    """Formats ActionItems for terminal and markdown output."""

    WARNING_ICON = "\\[!]"
    ERROR_ICON = "\\[x]"
    WARNING_COLOR = "yellow"
    ERROR_COLOR = "red"

    @classmethod
    def rich(cls, item: ActionItem) -> str:
        """Rich-markup line suitable for `console.print`."""
        icon = cls.WARNING_ICON if item.severity == "warning" else cls.ERROR_ICON
        color = cls.WARNING_COLOR if item.severity == "warning" else cls.ERROR_COLOR
        return f"  [{color}]{icon}[/{color}] {escape(item.message)}"

    @classmethod
    def markdown(cls, item: ActionItem) -> str:
        """Single-line markdown bullet."""
        label = "Warning" if item.severity == "warning" else "Error"
        prefix = f"**{item.package}**: " if item.package else ""
        return f"- [{label}] {prefix}{item.message}"


class IncompatiblePairFormatter:
    """Formats incompatible license pairs for terminal and markdown output."""

    ICON = "\\[x]"
    COLOR = "red"

    @classmethod
    def rich(cls, pair: CompatibilityResult) -> str:
        """Rich-markup line for `console.print`."""
        return (
            f"  [{cls.COLOR}]{cls.ICON}[/{cls.COLOR}] "
            f"{pair.inbound} <-> {pair.outbound}"
        )

    @classmethod
    def markdown_row(cls, pair: CompatibilityResult) -> str:
        """Markdown table row for a compatibility table."""
        return f"| {pair.inbound} | {pair.outbound} | {pair.verdict.value} |"
