"""Tests for RequirementsSource."""

from pathlib import Path

import pytest

from license_audit.sources.requirements import RequirementsSource


class TestRequirementsSource:
    def test_parse_basic(self, tmp_path: Path) -> None:
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("click>=8.1.0\nrich==13.9.4\npydantic\n")
        source = RequirementsSource(req_file)
        specs = source.parse()
        assert len(specs) == 3
        names = {s.name for s in specs}
        assert names == {"click", "rich", "pydantic"}

    def test_pinned_versions(self, tmp_path: Path) -> None:
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("click==8.1.7\n")
        source = RequirementsSource(req_file)
        specs = source.parse()
        assert specs[0].name == "click"
        assert specs[0].version_constraint == "==8.1.7"

    def test_skips_comments_and_flags(self, tmp_path: Path) -> None:
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("# a comment\n-r other.txt\nclick\n\n")
        source = RequirementsSource(req_file)
        specs = source.parse()
        assert len(specs) == 1
        assert specs[0].name == "click"

    def test_missing_file(self, tmp_path: Path) -> None:
        source = RequirementsSource(tmp_path / "requirements.txt")
        with pytest.raises(FileNotFoundError):
            source.parse()

    def test_canonicalizes_names(self, tmp_path: Path) -> None:
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("My-Package>=1.0\n")
        source = RequirementsSource(req_file)
        specs = source.parse()
        assert specs[0].name == "my_package"
