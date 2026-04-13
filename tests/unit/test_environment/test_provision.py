"""Tests for environment provisioning."""

from pathlib import Path

import pytest

from license_audit.environment.provision import (
    is_venv_dir,
    provision_current_env,
    provision_from_venv,
)


class TestProvisionCurrentEnv:
    def test_returns_site_packages(self) -> None:
        env = provision_current_env()
        assert env.site_packages.exists()
        assert "site-packages" in str(env.site_packages)

    def test_no_cleanup_needed(self) -> None:
        env = provision_current_env()
        with env:
            pass  # Should not raise


class TestProvisionFromVenv:
    def test_own_venv(self) -> None:
        """Point at license_audit's own .venv."""
        venv_path = Path(__file__).parent.parent.parent.parent / ".venv"
        if not venv_path.exists():
            pytest.skip(".venv not found")
        env = provision_from_venv(venv_path)
        assert env.site_packages.exists()
        # Should find dist-info dirs
        dist_infos = list(env.site_packages.glob("*.dist-info"))
        assert len(dist_infos) > 0

    def test_missing_venv(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            provision_from_venv(tmp_path / "nonexistent")


class TestIsVenvDir:
    def test_own_venv(self) -> None:
        venv_path = Path(__file__).parent.parent.parent.parent / ".venv"
        if not venv_path.exists():
            pytest.skip(".venv not found")
        assert is_venv_dir(venv_path)

    def test_project_dir_is_not_venv(self) -> None:
        project_dir = Path(__file__).parent.parent.parent.parent
        assert not is_venv_dir(project_dir)

    def test_nonexistent_is_not_venv(self, tmp_path: Path) -> None:
        assert not is_venv_dir(tmp_path / "nonexistent")
