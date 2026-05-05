"""Tests for the LicenseAuditor orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from license_audit.config import LicenseAuditConfig
from license_audit.core.analyzer import LicenseAuditor, TargetInfo
from license_audit.core.models import (
    UNKNOWN_LICENSE,
    LicenseCategory,
    PackageLicense,
)


class TestRun:
    def test_self_analysis(self) -> None:
        """Analyze license-audit's own dependencies via its .venv."""
        project_dir = Path(__file__).parents[2]
        report = LicenseAuditor().run(target=project_dir)
        assert report.project_name == "license-audit"
        assert len(report.packages) > 0
        assert report.policy_passed is not None
        # source should point at the resolved dependency file inside the project.
        assert report.source
        assert "license-audit" in report.source or str(project_dir) in report.source

    def test_unknown_project(self, tmp_path: Path) -> None:
        """Empty directory with no source files raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            LicenseAuditor().run(target=tmp_path)

    def test_no_target_uses_current_env(self) -> None:
        report = LicenseAuditor().run()
        assert report.project_name is not None
        assert report.source == "active environment"


class TestDescribeSource:
    def test_source_path_wins(self, tmp_path: Path) -> None:
        info = TargetInfo(source_path=tmp_path / "uv.lock", config_dir=tmp_path)
        assert LicenseAuditor._describe_source(info) == str(tmp_path / "uv.lock")

    def test_site_packages_when_no_source(self, tmp_path: Path) -> None:
        info = TargetInfo(site_packages=tmp_path / ".venv", config_dir=tmp_path)
        assert LicenseAuditor._describe_source(info) == str(tmp_path / ".venv")

    def test_active_environment_fallback(self) -> None:
        assert LicenseAuditor._describe_source(TargetInfo()) == "active environment"


class TestWarnIfGroupsIgnored:
    def test_warns_when_groups_set_and_no_target(self) -> None:
        config = LicenseAuditConfig(dependency_groups=["main"])
        info = TargetInfo()
        with pytest.warns(UserWarning, match="dependency-groups is configured"):
            LicenseAuditor()._warn_if_groups_ignored(info, config)

    def test_no_warning_when_source_resolved(self, tmp_path: Path) -> None:
        config = LicenseAuditConfig(dependency_groups=["main"])
        info = TargetInfo(source_path=tmp_path / "uv.lock", config_dir=tmp_path)
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("error")
            LicenseAuditor()._warn_if_groups_ignored(info, config)

    def test_no_warning_when_groups_unset(self) -> None:
        config = LicenseAuditConfig()
        info = TargetInfo()
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("error")
            LicenseAuditor()._warn_if_groups_ignored(info, config)


class TestClassifyPackage:
    def test_single_license(self) -> None:
        pkg = PackageLicense(name="a", version="1.0", license_expression="MIT")
        auditor = LicenseAuditor()
        auditor._classify_package(pkg)
        assert pkg.category == LicenseCategory.PERMISSIVE

    def test_or_expression_picks_most_permissive(self) -> None:
        pkg = PackageLicense(
            name="a",
            version="1.0",
            license_expression="MIT OR GPL-3.0-only",
        )
        auditor = LicenseAuditor()
        auditor._classify_package(pkg)
        assert pkg.category == LicenseCategory.PERMISSIVE

    def test_and_expression_picks_most_restrictive(self) -> None:
        pkg = PackageLicense(
            name="tqdm",
            version="4.67",
            license_expression="MPL-2.0 AND MIT",
        )
        auditor = LicenseAuditor()
        auditor._classify_package(pkg)
        assert pkg.category == LicenseCategory.WEAK_COPYLEFT

    def test_nested_and_over_or(self) -> None:
        pkg = PackageLicense(
            name="orjson",
            version="3.11",
            license_expression="MPL-2.0 AND (Apache-2.0 OR MIT)",
        )
        auditor = LicenseAuditor()
        auditor._classify_package(pkg)
        assert pkg.category == LicenseCategory.WEAK_COPYLEFT


class TestExtractSpdxIds:
    def test_skips_unknown(self) -> None:
        auditor = LicenseAuditor()
        result = auditor._extract_spdx_ids(["MIT", UNKNOWN_LICENSE, "Apache-2.0"])
        assert "MIT" in result
        assert "Apache-2.0" in result
        assert UNKNOWN_LICENSE not in result

    def test_empty_list(self) -> None:
        assert LicenseAuditor()._extract_spdx_ids([]) == []

    def test_or_expression_only_contributes_chosen_branch(self) -> None:
        result = LicenseAuditor()._extract_spdx_ids(["GPL-3.0-only OR MIT"])
        assert "MIT" in result
        assert "GPL-3.0-only" not in result

    def test_and_expression_contributes_all_components(self) -> None:
        result = LicenseAuditor()._extract_spdx_ids(["MPL-2.0 AND MIT"])
        assert "MPL-2.0" in result
        assert "MIT" in result
