"""Rich terminal output for analysis reports."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from license_audit.core.models import UNKNOWN_LICENSE, AnalysisReport, LicenseCategory

_CATEGORY_COLORS: dict[LicenseCategory, str] = {
    LicenseCategory.PERMISSIVE: "green",
    LicenseCategory.WEAK_COPYLEFT: "yellow",
    LicenseCategory.STRONG_COPYLEFT: "red",
    LicenseCategory.NETWORK_COPYLEFT: "bright_red",
    LicenseCategory.PROPRIETARY: "magenta",
    LicenseCategory.UNKNOWN: "dim",
}


class TerminalRenderer:
    """Render analysis report to the terminal using Rich."""

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    def render(self, report: AnalysisReport) -> str:
        """Render the report to the console and return empty string."""
        self._render_header(report)
        self._render_package_table(report)
        self._render_compatibility(report)
        self._render_recommendations(report)
        self._render_action_items(report)
        self._render_summary(report)
        return ""

    def _render_header(self, report: AnalysisReport) -> None:
        self._console.print()
        self._console.rule(f"[bold]License Analysis: {report.project_name}[/bold]")
        self._console.print()

    def _render_package_table(self, report: AnalysisReport) -> None:
        table = Table(title="Dependency Licenses", show_lines=False)
        table.add_column("Package", style="cyan")
        table.add_column("Version", style="dim")
        table.add_column("License", style="bold")
        table.add_column("Category")
        table.add_column("Source", style="dim")
        table.add_column("Parent", style="dim")

        for pkg in sorted(report.packages, key=lambda p: p.name):
            color = _CATEGORY_COLORS.get(pkg.category, "white")
            category_text = Text(pkg.category.value, style=color)
            parent = pkg.parent if pkg.parent != pkg.name else "(direct)"
            table.add_row(
                pkg.name,
                pkg.version,
                pkg.license_expression,
                category_text,
                pkg.license_source.value,
                parent,
            )

        self._console.print(table)
        self._console.print()

    def _render_compatibility(self, report: AnalysisReport) -> None:
        if not report.incompatible_pairs:
            return

        self._console.print("[bold red]Incompatible License Pairs:[/bold red]")
        for pair in report.incompatible_pairs:
            self._console.print(
                f"  [red]\\[x][/red] {pair.inbound} <-> {pair.outbound}"
            )
        self._console.print()

    def _render_recommendations(self, report: AnalysisReport) -> None:
        if not report.recommended_licenses:
            self._console.print(
                "[bold red]No compatible outbound license found![/bold red]"
            )
            if report.incompatible_pairs:
                for pair in report.incompatible_pairs:
                    self._console.print(
                        f"  [red]\\[x][/red] {pair.inbound} and {pair.outbound} "
                        "have no common outbound license"
                    )
            self._console.print()
            return

        self._console.print(
            "[bold]Recommended Outbound Licenses[/bold] (most -> least permissive):"
        )
        for i, lic in enumerate(report.recommended_licenses[:10]):
            marker = "->" if i == 0 else "  "
            if i == 0:
                self._console.print(f"  {marker} [bold green]{lic}[/bold green]")
            else:
                self._console.print(f"  {marker} {lic}")
        if len(report.recommended_licenses) > 10:
            self._console.print(
                f"  ... and {len(report.recommended_licenses) - 10} more"
            )
        self._console.print()

    def _render_action_items(self, report: AnalysisReport) -> None:
        if not report.action_items:
            return

        self._console.print("[bold]Action Items:[/bold]")
        for item in report.action_items:
            icon = "\\[!]" if item.severity == "warning" else "\\[x]"
            color = "yellow" if item.severity == "warning" else "red"
            self._console.print(f"  [{color}]{icon}[/{color}] {escape(item.message)}")
        self._console.print()

    def _render_summary(self, report: AnalysisReport) -> None:
        total = len(report.packages)
        unknown = sum(
            1 for p in report.packages if p.license_expression == UNKNOWN_LICENSE
        )
        copyleft = sum(
            1
            for p in report.packages
            if p.category
            in (
                LicenseCategory.STRONG_COPYLEFT,
                LicenseCategory.WEAK_COPYLEFT,
                LicenseCategory.NETWORK_COPYLEFT,
            )
        )

        self._console.rule("[bold]Summary[/bold]")
        self._console.print(f"  Total dependencies: {total}")
        self._console.print(f"  Unknown licenses:   {unknown}")
        self._console.print(f"  Copyleft licenses:  {copyleft}")

        if report.policy_passed is not None:
            if report.policy_passed:
                self._console.print(
                    "  Policy check:       [bold green]PASSED[/bold green]"
                )
            else:
                self._console.print("  Policy check:       [bold red]FAILED[/bold red]")

        self._console.print()
