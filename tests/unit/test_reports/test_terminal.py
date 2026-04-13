"""Tests for terminal renderer."""

from io import StringIO

from rich.console import Console

from license_audit.core.models import AnalysisReport
from license_audit.reports.terminal import TerminalRenderer


class TestTerminalRenderer:
    def test_render_returns_string(self, sample_report: AnalysisReport) -> None:
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        renderer = TerminalRenderer(console=console)
        result = renderer.render(sample_report)
        assert result == ""
        output = buf.getvalue()
        assert "test-project" in output
        assert "test-pkg" in output

    def test_empty_report(self) -> None:
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        renderer = TerminalRenderer(console=console)
        report = AnalysisReport(project_name="empty")
        renderer.render(report)
        output = buf.getvalue()
        assert "empty" in output

    def test_incompatible_pairs_shown(self) -> None:
        from license_audit.core.models import CompatibilityResult, Verdict

        buf = StringIO()
        console = Console(file=buf, width=120)
        renderer = TerminalRenderer(console=console)
        report = AnalysisReport(
            project_name="conflict",
            incompatible_pairs=[
                CompatibilityResult(
                    inbound="GPL-2.0-only",
                    outbound="Apache-2.0",
                    verdict=Verdict.INCOMPATIBLE,
                )
            ],
        )
        renderer.render(report)
        output = buf.getvalue()
        assert "GPL-2.0-only" in output
        assert "Apache-2.0" in output

    def test_no_recommendations(self) -> None:
        from license_audit.core.models import CompatibilityResult, Verdict

        buf = StringIO()
        console = Console(file=buf, width=120)
        renderer = TerminalRenderer(console=console)
        report = AnalysisReport(
            project_name="no-compat",
            recommended_licenses=[],
            incompatible_pairs=[
                CompatibilityResult(
                    inbound="GPL-2.0-only",
                    outbound="Apache-2.0",
                    verdict=Verdict.INCOMPATIBLE,
                )
            ],
        )
        renderer.render(report)
        output = buf.getvalue()
        assert "No compatible outbound license found" in output

    def test_many_recommendations_truncated(self) -> None:
        buf = StringIO()
        console = Console(file=buf, width=120)
        renderer = TerminalRenderer(console=console)
        report = AnalysisReport(
            project_name="many",
            recommended_licenses=[f"License-{i}" for i in range(15)],
        )
        renderer.render(report)
        output = buf.getvalue()
        assert "and 5 more" in output

    def test_policy_failed_shown(self) -> None:
        buf = StringIO()
        console = Console(file=buf, width=120)
        renderer = TerminalRenderer(console=console)
        report = AnalysisReport(
            project_name="fail",
            policy_passed=False,
        )
        renderer.render(report)
        output = buf.getvalue()
        assert "FAILED" in output
