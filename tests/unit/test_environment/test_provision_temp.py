"""Tests for temporary environment provisioning."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from license_audit.environment.provision import (
    ProvisionedEnv,
    _find_python,
    _spec_to_install_arg,
    check_uv_available,
    provision_temp_env,
)
from license_audit.sources.base import PackageSpec


class TestCheckUvAvailable:
    def test_returns_true_when_uv_on_path(self):
        with patch(
            "license_audit.environment.provision.shutil.which",
            return_value="/usr/bin/uv",
        ):
            assert check_uv_available() is True

    def test_returns_false_when_uv_missing(self):
        with patch(
            "license_audit.environment.provision.shutil.which", return_value=None
        ):
            assert check_uv_available() is False


class TestSpecToInstallArg:
    def test_registry_package(self):
        spec = PackageSpec(name="click", version_constraint=">=8.0")
        assert _spec_to_install_arg(spec) == "click>=8.0"

    def test_url_package(self):
        spec = PackageSpec(
            name="mypkg",
            version_constraint="",
            source_url="git+https://github.com/user/mypkg.git",
        )
        assert (
            _spec_to_install_arg(spec)
            == "mypkg @ git+https://github.com/user/mypkg.git"
        )

    def test_no_version_constraint(self):
        spec = PackageSpec(name="click", version_constraint="")
        assert _spec_to_install_arg(spec) == "click"


class TestFindPython:
    def test_finds_unix_python(self, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        python = bin_dir / "python"
        python.touch()
        assert _find_python(tmp_path) == python

    def test_finds_windows_python(self, tmp_path):
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir()
        python = scripts_dir / "python.exe"
        python.touch()
        assert _find_python(tmp_path) == python

    def test_raises_if_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Python executable not found"):
            _find_python(tmp_path)


class TestProvisionTempEnv:
    def test_raises_when_uv_missing(self):
        with (
            patch(
                "license_audit.environment.provision.check_uv_available",
                return_value=False,
            ),
            pytest.raises(RuntimeError, match="uv"),
        ):
            provision_temp_env([])

    def test_raises_on_venv_creation_failure(self):
        with (
            patch(
                "license_audit.environment.provision.check_uv_available",
                return_value=True,
            ),
            patch(
                "license_audit.environment.provision.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    1, "uv", stderr="venv failed"
                ),
            ),
            pytest.raises(RuntimeError, match="Failed to provision"),
        ):
            provision_temp_env([PackageSpec(name="click", version_constraint=">=8.0")])


class TestProvisionedEnvCleanup:
    def test_cleanup_is_idempotent(self, tmp_path):
        mock_tmp = MagicMock()
        env = ProvisionedEnv(site_packages=tmp_path, _tmp_dir=mock_tmp)
        env.cleanup()
        env.cleanup()
        mock_tmp.cleanup.assert_called_once()

    def test_context_manager_calls_cleanup(self, tmp_path):
        mock_tmp = MagicMock()
        env = ProvisionedEnv(site_packages=tmp_path, _tmp_dir=mock_tmp)
        with env:
            pass
        mock_tmp.cleanup.assert_called_once()

    def test_no_tmp_dir_cleanup_safe(self, tmp_path):
        env = ProvisionedEnv(site_packages=tmp_path)
        env.cleanup()  # Should not raise
