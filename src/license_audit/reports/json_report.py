"""JSON report renderer."""

from __future__ import annotations

from license_audit.core.models import AnalysisReport


class JsonRenderer:
    """Render analysis report as JSON."""

    def render(self, report: AnalysisReport) -> str:
        """Render the report as a JSON string."""
        return report.model_dump_json(indent=2)
