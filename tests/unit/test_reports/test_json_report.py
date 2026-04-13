"""Tests for JSON renderer."""

import json

from license_audit.core.models import AnalysisReport
from license_audit.reports.json_report import JsonRenderer


class TestJsonRenderer:
    def test_valid_json(self, sample_report: AnalysisReport) -> None:
        renderer = JsonRenderer()
        result = renderer.render(sample_report)
        data = json.loads(result)
        assert data["project_name"] == "test-project"
        assert len(data["packages"]) == 2

    def test_empty_report(self) -> None:
        renderer = JsonRenderer()
        result = renderer.render(AnalysisReport())
        data = json.loads(result)
        assert data["packages"] == []
