"""Tests for EnvironmentProvisioner.temp() and helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from license_audit.environment.provision import (
    EnvironmentProvisioner,
    ProvisionedEnv,
)
from license_audit.sources.base import PackageSpec


class TestCheckUvAvailable:
    def test_true_when_uv_on_path(self) -> None:
        with patch(
            "license_audit.environment.provision.shutil.which",
            return_value="/usr/bin/uv",
        ):
            assert EnvironmentProvisioner().check_uv_available() is True

    def test_false_when_uv_missing(self) -> None:
        with patch(
            "license_audit.environment.provision.shutil.which",
            return_value=None,
        ):
            assert EnvironmentProvisioner().check_uv_available() is False


class TestSpecToInstallArg:
    def test_registry_package(self) -> None:
        spec = PackageSpec(name="click", version_constraint=">=8.0")
        assert EnvironmentProvisioner._spec_to_install_arg(spec) == "click>=8.0"

    def test_url_package(self) -> None:
        spec = PackageSpec(
            name="mypkg",
            version_constraint="",
            source_url="git+https://github.com/user/mypkg.git",
        )
        assert (
            EnvironmentProvisioner._spec_to_install_arg(spec)
            == "mypkg @ git+https://github.com/user/mypkg.git"
        )

    def test_no_version_constraint(self) -> None:
        spec = PackageSpec(name="click", version_constraint="")
        assert EnvironmentProvisioner._spec_to_install_arg(spec) == "click"


class TestFindPython:
    def test_unix_python(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        python = bin_dir / "python"
        python.touch()
        assert EnvironmentProvisioner._find_python(tmp_path) == python

    def test_windows_python(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir()
        python = scripts_dir / "python.exe"
        python.touch()
        assert EnvironmentProvisioner._find_python(tmp_path) == python

    def test_raises_if_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Python executable not found"):
            EnvironmentProvisioner._find_python(tmp_path)


class TestTemp:
    def test_raises_when_uv_missing(self) -> None:
        provisioner = EnvironmentProvisioner()
        with (
            patch.object(provisioner, "check_uv_available", return_value=False),
            pytest.raises(RuntimeError, match="uv"),
        ):
            provisioner.temp([])

    def test_raises_on_venv_creation_failure(self) -> None:
        provisioner = EnvironmentProvisioner()
        with (
            patch.object(provisioner, "check_uv_available", return_value=True),
            patch(
                "license_audit.environment.provision.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    1,
                    "uv",
                    stderr="venv failed",
                ),
            ),
            pytest.raises(RuntimeError, match="Failed to provision"),
        ):
            provisioner.temp([PackageSpec(name="click", version_constraint=">=8.0")])

    def test_cleans_up_on_early_failure(self) -> None:
        provisioner = EnvironmentProvisioner()
        created_tmp_dirs: list[MagicMock] = []

        original_tempdir = __import__(
            "license_audit.environment.provision",
            fromlist=["tempfile"],
        ).tempfile.TemporaryDirectory

        def fake_tempdir(*args: object, **kwargs: object) -> MagicMock:
            mock = MagicMock(wraps=original_tempdir(*args, **kwargs))
            created_tmp_dirs.append(mock)
            return mock

        with (
            patch.object(provisioner, "check_uv_available", return_value=True),
            patch(
                "license_audit.environment.provision.tempfile.TemporaryDirectory",
                side_effect=fake_tempdir,
            ),
            patch(
                "license_audit.environment.provision.atexit.unregister",
            ) as mock_unregister,
            patch(
                "license_audit.environment.provision.subprocess.run",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            provisioner.temp([PackageSpec(name="click", version_constraint=">=8.0")])

        assert len(created_tmp_dirs) == 1
        created_tmp_dirs[0].cleanup.assert_called()
        mock_unregister.assert_called_once_with(created_tmp_dirs[0].cleanup)


class TestProvisionedEnvCleanup:
    def test_cleanup_is_idempotent(self, tmp_path: Path) -> None:
        mock_tmp = MagicMock()
        env = ProvisionedEnv(site_packages=tmp_path, _tmp_dir=mock_tmp)
        env.cleanup()
        env.cleanup()
        mock_tmp.cleanup.assert_called_once()

    def test_context_manager_calls_cleanup(self, tmp_path: Path) -> None:
        mock_tmp = MagicMock()
        env = ProvisionedEnv(site_packages=tmp_path, _tmp_dir=mock_tmp)
        with env:
            pass
        mock_tmp.cleanup.assert_called_once()

    def test_no_tmp_dir_cleanup_safe(self, tmp_path: Path) -> None:
        env = ProvisionedEnv(site_packages=tmp_path)
        env.cleanup()  # Should not raise

    def test_cleanup_unregisters_atexit(self, tmp_path: Path) -> None:
        """Explicit cleanup removes the atexit safety net to prevent accumulation."""
        mock_tmp = MagicMock()
        env = ProvisionedEnv(site_packages=tmp_path, _tmp_dir=mock_tmp)
        with patch(
            "license_audit.environment.provision.atexit.unregister",
        ) as mock_unregister:
            env.cleanup()
        mock_unregister.assert_called_once_with(mock_tmp.cleanup)
