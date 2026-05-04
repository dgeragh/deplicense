"""Tests for cli._common.resolve_config."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from license_audit.cli._common import resolve_config
from license_audit.core.models import PolicyLevel


def _ctx(
    target: Path | None = None,
    policy: str | None = None,
    dependency_groups: tuple[str, ...] = (),
) -> SimpleNamespace:
    """A minimal click.Context stand-in exposing just ``obj``."""
    return SimpleNamespace(
        obj={
            "target": target,
            "policy": policy,
            "dependency_groups": dependency_groups,
        },
    )


class TestResolveConfig:
    def test_no_target_uses_cwd_defaults(self) -> None:
        target, config = resolve_config(_ctx())  # type: ignore[arg-type]
        assert target is None
        assert config.policy == PolicyLevel.PERMISSIVE

    def test_directory_target_loads_config_from_it(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.license-audit]\npolicy = "weak-copyleft"\n',
        )
        target, config = resolve_config(_ctx(target=tmp_path))  # type: ignore[arg-type]
        assert target == tmp_path
        assert config.policy == PolicyLevel.WEAK_COPYLEFT

    def test_file_target_uses_parent_dir_for_config(self, tmp_path: Path) -> None:
        """A file target causes ``config_dir`` to be the file's parent."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.license-audit]\npolicy = "strong-copyleft"\n',
        )
        lock = tmp_path / "uv.lock"
        lock.write_text("version = 1\n")
        target, config = resolve_config(_ctx(target=lock))  # type: ignore[arg-type]
        assert target == lock
        assert config.policy == PolicyLevel.STRONG_COPYLEFT

    def test_policy_flag_overrides_config(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.license-audit]\npolicy = "permissive"\n',
        )
        _target, config = resolve_config(
            _ctx(target=tmp_path, policy="network-copyleft"),  # type: ignore[arg-type]
        )
        assert config.policy == PolicyLevel.NETWORK_COPYLEFT

    def test_dependency_groups_flag_overrides_config(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.license-audit]\ndependency-groups = ["main"]\n',
        )
        _target, config = resolve_config(
            _ctx(target=tmp_path, dependency_groups=("dev", "optional:docs")),  # type: ignore[arg-type]
        )
        assert config.dependency_groups == ["dev", "optional:docs"]

    def test_empty_dependency_groups_tuple_leaves_config_default(
        self,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.license-audit]\ndependency-groups = ["main"]\n',
        )
        _target, config = resolve_config(
            _ctx(target=tmp_path, dependency_groups=()),  # type: ignore[arg-type]
        )
        assert config.dependency_groups == ["main"]

    def test_config_target_used_when_cli_target_absent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`target` in `[tool.license-audit]` is used when --target is omitted."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / "pyproject.toml").write_text(
            '[tool.license-audit]\ntarget = "."\n',
        )
        # CWD is the project so load_config(None) finds this pyproject.
        monkeypatch.chdir(project)
        target, config = resolve_config(_ctx())  # type: ignore[arg-type]
        assert config.target == "."
        assert target == project.resolve()

    def test_config_target_resolved_against_pyproject_dir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Relative `target` resolves against the pyproject's directory."""
        project = tmp_path / "proj"
        project.mkdir()
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        (project / "pyproject.toml").write_text(
            '[tool.license-audit]\ntarget = "../sibling"\n',
        )
        # CWD is the project; CLI target absent so config.target kicks in.
        monkeypatch.chdir(project)
        target, _config = resolve_config(_ctx())  # type: ignore[arg-type]
        assert target == sibling.resolve()

    def test_cli_target_overrides_config_target(
        self,
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        (project / "pyproject.toml").write_text(
            '[tool.license-audit]\ntarget = "/should/be/ignored"\n',
        )
        target, _config = resolve_config(_ctx(target=project))  # type: ignore[arg-type]
        assert target == project
