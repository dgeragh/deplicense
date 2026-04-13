"""Abstract base for report renderers."""

from __future__ import annotations

from typing import Protocol

from license_audit.core.models import AnalysisReport


class ReportRenderer(Protocol):
    """Protocol for report renderers."""

    def render(self, report: AnalysisReport) -> str:
        """Render an analysis report to a string."""
        ...
