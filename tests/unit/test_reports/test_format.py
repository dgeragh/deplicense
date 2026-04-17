"""Tests for shared report formatters."""

from __future__ import annotations

from license_audit.core.models import ActionItem, CompatibilityResult, Verdict
from license_audit.reports._format import (
    ActionItemFormatter,
    IncompatiblePairFormatter,
)


class TestActionItemFormatterRich:
    def test_warning_uses_yellow(self) -> None:
        item = ActionItem(severity="warning", message="watch out")
        result = ActionItemFormatter.rich(item)
        assert "[yellow]" in result
        assert "watch out" in result

    def test_error_uses_red(self) -> None:
        item = ActionItem(severity="error", message="nope")
        result = ActionItemFormatter.rich(item)
        assert "[red]" in result
        assert "nope" in result

    def test_message_is_escaped(self) -> None:
        """Rich markup characters in the message are escaped to avoid
        accidentally styling user-supplied text."""
        item = ActionItem(severity="warning", message="[x] not markup")
        result = ActionItemFormatter.rich(item)
        # Escaped form prefixes open-brackets with a backslash.
        assert r"\[x]" in result


class TestActionItemFormatterMarkdown:
    def test_warning_label(self) -> None:
        item = ActionItem(severity="warning", message="heads up")
        result = ActionItemFormatter.markdown(item)
        assert result.startswith("- [Warning]")
        assert "heads up" in result

    def test_error_label(self) -> None:
        item = ActionItem(severity="error", message="broken")
        result = ActionItemFormatter.markdown(item)
        assert result.startswith("- [Error]")

    def test_package_prefix_when_set(self) -> None:
        item = ActionItem(severity="error", package="foo", message="x")
        assert "**foo**: x" in ActionItemFormatter.markdown(item)

    def test_no_prefix_when_package_empty(self) -> None:
        item = ActionItem(severity="error", message="x")
        assert "**" not in ActionItemFormatter.markdown(item)


class TestIncompatiblePairFormatter:
    def _pair(self) -> CompatibilityResult:
        return CompatibilityResult(
            inbound="GPL-2.0-only",
            outbound="Apache-2.0",
            verdict=Verdict.INCOMPATIBLE,
        )

    def test_rich(self) -> None:
        result = IncompatiblePairFormatter.rich(self._pair())
        assert "[red]" in result
        assert "GPL-2.0-only" in result
        assert "Apache-2.0" in result

    def test_markdown_row(self) -> None:
        result = IncompatiblePairFormatter.markdown_row(self._pair())
        assert result == "| GPL-2.0-only | Apache-2.0 | incompatible |"
