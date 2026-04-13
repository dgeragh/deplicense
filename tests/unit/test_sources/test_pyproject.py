"""Tests for PyprojectSource."""

from pathlib import Path

import pytest

from license_audit.sources.pyproject import PyprojectSource


class TestPyprojectSource:
    def test_parse_dependencies(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "test-project"\n'
            "dependencies = [\n"
            '    "click>=8.1.0",\n'
            '    "rich>=13.0.0",\n'
            "]\n"
        )
        source = PyprojectSource(pyproject)
        specs = source.parse()
        assert len(specs) == 2
        names = {s.name for s in specs}
        assert names == {"click", "rich"}

    def test_version_constraints(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["click>=8.1.0,<9"]\n')
        source = PyprojectSource(pyproject)
        specs = source.parse()
        assert specs[0].name == "click"
        assert ">=8.1.0" in specs[0].version_constraint

    def test_no_dependencies(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "empty"\n')
        source = PyprojectSource(pyproject)
        specs = source.parse()
        assert specs == []

    def test_missing_file(self, tmp_path: Path) -> None:
        source = PyprojectSource(tmp_path / "pyproject.toml")
        with pytest.raises(FileNotFoundError):
            source.parse()

    def test_canonicalizes_names(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["My-Package>=1.0"]\n')
        source = PyprojectSource(pyproject)
        specs = source.parse()
        assert specs[0].name == "my_package"

    def test_optional_dependencies(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'dependencies = ["click"]\n'
            "\n"
            "[project.optional-dependencies]\n"
            'dev = ["pytest"]\n'
        )
        source = PyprojectSource(pyproject)
        specs = source.parse()
        names = {s.name for s in specs}
        assert "click" in names
        assert "pytest" in names

    def test_dependency_groups(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'dependencies = ["click"]\n'
            "\n"
            "[dependency-groups]\n"
            'test = ["pytest"]\n'
        )
        source = PyprojectSource(pyproject)
        specs = source.parse()
        names = {s.name for s in specs}
        assert "click" in names
        assert "pytest" in names

    def test_uv_dev_dependencies(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'dependencies = ["click"]\n'
            "\n"
            "[tool.uv]\n"
            'dev-dependencies = ["ruff"]\n'
        )
        source = PyprojectSource(pyproject)
        specs = source.parse()
        names = {s.name for s in specs}
        assert "click" in names
        assert "ruff" in names

    def test_deduplicates_across_sections(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'dependencies = ["click>=8.0"]\n'
            "\n"
            "[dependency-groups]\n"
            'dev = ["click>=8.1"]\n'
        )
        source = PyprojectSource(pyproject)
        specs = source.parse()
        click_specs = [s for s in specs if s.name == "click"]
        assert len(click_specs) == 1


_ALL_GROUPS_TOML = (
    "[project]\n"
    'name = "test"\n'
    'dependencies = ["click"]\n'
    "\n"
    "[project.optional-dependencies]\n"
    'api = ["fastapi"]\n'
    'docs = ["sphinx"]\n'
    "\n"
    "[dependency-groups]\n"
    'test = ["pytest"]\n'
    'lint = ["ruff"]\n'
    "\n"
    "[tool.uv]\n"
    'dev-dependencies = ["ipython"]\n'
)


class TestPyprojectSourceGroupFiltering:
    def _names(self, tmp_path: Path, groups: list[str] | None) -> set[str]:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(_ALL_GROUPS_TOML)
        source = PyprojectSource(pyproject, groups=groups)
        return {s.name for s in source.parse()}

    def test_none_includes_all(self, tmp_path: Path) -> None:
        names = self._names(tmp_path, None)
        assert names == {"click", "fastapi", "sphinx", "pytest", "ruff", "ipython"}

    def test_main_only(self, tmp_path: Path) -> None:
        names = self._names(tmp_path, ["main"])
        assert names == {"click"}

    def test_optional_specific(self, tmp_path: Path) -> None:
        names = self._names(tmp_path, ["optional:api"])
        assert names == {"fastapi"}

    def test_group_specific(self, tmp_path: Path) -> None:
        names = self._names(tmp_path, ["group:test"])
        assert names == {"pytest"}

    def test_dev_only(self, tmp_path: Path) -> None:
        names = self._names(tmp_path, ["dev"])
        assert names == {"ipython"}

    def test_main_and_optional(self, tmp_path: Path) -> None:
        names = self._names(tmp_path, ["main", "optional:api"])
        assert names == {"click", "fastapi"}

    def test_excludes_unselected_optional(self, tmp_path: Path) -> None:
        names = self._names(tmp_path, ["main", "optional:api"])
        assert "sphinx" not in names

    def test_excludes_unselected_group(self, tmp_path: Path) -> None:
        names = self._names(tmp_path, ["main", "group:test"])
        assert "ruff" not in names
        assert "pytest" in names
