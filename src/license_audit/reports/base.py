"""Protocols for report renderers.

String renderers return the full output so callers can write it to a file
or echo it. Console renderers write directly to a Rich console and return
``None`` — they cannot be captured as a string without a recording console.
"""

from __future__ import annotations

from typing import Protocol

from license_audit.core.models import AnalysisReport


class StringRenderer(Protocol):
    """Renderer that returns the report as a string."""

    def render(self, report: AnalysisReport) -> str:
        """Render an analysis report to a string."""
        ...


class ConsoleRenderer(Protocol):
    """Renderer that writes directly to a Rich console."""

    def render(self, report: AnalysisReport) -> None:
        """Render an analysis report to the attached console."""
        ...
