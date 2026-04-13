"""Tests for configuration loading."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from license_audit.config import LicenseAuditConfig, get_project_name, load_config


class TestLoadConfig:
    def test_defaults(self, tmp_path: Path) -> None:
        config = load_config(tmp_path)
        assert config.fail_on_unknown is True
        assert config.policy == "permissive"
        assert config.allowed_licenses == []
        assert config.denied_licenses == []
        assert config.overrides == {}
        assert config.dependency_groups is None

    def test_from_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.license-audit]\n"
            "fail-on-unknown = false\n"
            'policy = "strong-copyleft"\n'
            'allowed-licenses = ["MIT", "Apache-2.0"]\n'
            'denied-licenses = ["GPL-3.0-only"]\n'
            "\n"
            "[tool.license-audit.overrides]\n"
            'some-pkg = "MIT"\n'
        )
        config = load_config(tmp_path)
        assert config.fail_on_unknown is False
        assert config.policy == "strong-copyleft"
        assert config.allowed_licenses == ["MIT", "Apache-2.0"]
        assert config.denied_licenses == ["GPL-3.0-only"]
        assert config.overrides == {"some-pkg": "MIT"}

    def test_missing_section(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')
        config = load_config(tmp_path)
        assert config.fail_on_unknown is True

    def test_dependency_groups_from_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.license-audit]\ndependency-groups = ["main", "optional:api"]\n'
        )
        config = load_config(tmp_path)
        assert config.dependency_groups == ["main", "optional:api"]


class TestDependencyGroupsValidation:
    def test_none_is_valid(self) -> None:
        config = LicenseAuditConfig(dependency_groups=None)
        assert config.dependency_groups is None

    def test_main_is_valid(self) -> None:
        config = LicenseAuditConfig(dependency_groups=["main"])
        assert config.dependency_groups == ["main"]

    def test_dev_is_valid(self) -> None:
        config = LicenseAuditConfig(dependency_groups=["dev"])
        assert config.dependency_groups == ["dev"]

    def test_optional_prefix_is_valid(self) -> None:
        config = LicenseAuditConfig(dependency_groups=["optional:api"])
        assert config.dependency_groups == ["optional:api"]

    def test_group_prefix_is_valid(self) -> None:
        config = LicenseAuditConfig(dependency_groups=["group:test"])
        assert config.dependency_groups == ["group:test"]

    def test_multiple_valid_selectors(self) -> None:
        config = LicenseAuditConfig(
            dependency_groups=["main", "dev", "optional:docs", "group:lint"]
        )
        assert len(config.dependency_groups) == 4

    def test_invalid_selector_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid dependency group"):
            LicenseAuditConfig(dependency_groups=["bogus"])

    def test_empty_optional_prefix_rejected(self) -> None:
        with pytest.raises(ValidationError, match="missing name after prefix"):
            LicenseAuditConfig(dependency_groups=["optional:"])

    def test_empty_group_prefix_rejected(self) -> None:
        with pytest.raises(ValidationError, match="missing name after prefix"):
            LicenseAuditConfig(dependency_groups=["group:"])


class TestGetProjectName:
    def test_reads_name(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-cool-project"\n')
        assert get_project_name(tmp_path) == "my-cool-project"

    def test_missing_file(self, tmp_path: Path) -> None:
        assert get_project_name(tmp_path) == "unknown"
