"""Tests for TerminalRenderer."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from license_audit.core.models import (
    AnalysisReport,
    CompatibilityResult,
    Verdict,
)
from license_audit.reports.terminal import TerminalRenderer


def _make_console(*, force_terminal: bool = False) -> tuple[Console, StringIO]:
    buf = StringIO()
    console = Console(file=buf, force_terminal=force_terminal, width=120)
    return console, buf


class TestTerminalRenderer:
    def test_render_writes_to_console(self, sample_report: AnalysisReport) -> None:
        console, buf = _make_console(force_terminal=True)
        TerminalRenderer(console=console).render(sample_report)
        output = buf.getvalue()
        assert "test-project" in output
        assert "test-pkg" in output

    def test_empty_report(self) -> None:
        console, buf = _make_console(force_terminal=True)
        TerminalRenderer(console=console).render(AnalysisReport(project_name="empty"))
        assert "empty" in buf.getvalue()

    def test_incompatible_pairs_shown(self) -> None:
        console, buf = _make_console()
        report = AnalysisReport(
            project_name="conflict",
            incompatible_pairs=[
                CompatibilityResult(
                    inbound="GPL-2.0-only",
                    outbound="Apache-2.0",
                    verdict=Verdict.INCOMPATIBLE,
                ),
            ],
        )
        TerminalRenderer(console=console).render(report)
        output = buf.getvalue()
        assert "GPL-2.0-only" in output
        assert "Apache-2.0" in output

    def test_no_recommendations(self) -> None:
        console, buf = _make_console()
        report = AnalysisReport(
            project_name="no-compat",
            recommended_licenses=[],
            incompatible_pairs=[
                CompatibilityResult(
                    inbound="GPL-2.0-only",
                    outbound="Apache-2.0",
                    verdict=Verdict.INCOMPATIBLE,
                ),
            ],
        )
        TerminalRenderer(console=console).render(report)
        assert "No compatible outbound license found" in buf.getvalue()

    def test_many_recommendations_truncated(self) -> None:
        console, buf = _make_console()
        report = AnalysisReport(
            project_name="many",
            recommended_licenses=[f"License-{i}" for i in range(15)],
        )
        TerminalRenderer(console=console).render(report)
        assert "and 5 more" in buf.getvalue()

    def test_policy_failed_shown(self) -> None:
        console, buf = _make_console()
        TerminalRenderer(console=console).render(
            AnalysisReport(project_name="fail", policy_passed=False),
        )
        assert "FAILED" in buf.getvalue()

    def test_source_in_header(self) -> None:
        console, buf = _make_console()
        TerminalRenderer(console=console).render(
            AnalysisReport(project_name="p", source="/abs/uv.lock"),
        )
        assert "Source:" in buf.getvalue()
        assert "/abs/uv.lock" in buf.getvalue()
