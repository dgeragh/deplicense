"""Environment provisioning for license analysis."""

from __future__ import annotations

import atexit
import logging
import shutil
import subprocess
import sysconfig
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from license_audit.sources.base import PackageSpec

logger = logging.getLogger(__name__)


@dataclass
class ProvisionedEnv:
    """A provisioned Python environment ready for license analysis.

    Use as a context manager to ensure temp environments are cleaned up.
    """

    site_packages: Path
    _tmp_dir: tempfile.TemporaryDirectory[str] | None = field(default=None, repr=False)

    def cleanup(self) -> None:
        """Clean up the temporary environment, if any."""
        if self._tmp_dir is not None:
            self._tmp_dir.cleanup()
            self._tmp_dir = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.cleanup()


def provision_current_env() -> ProvisionedEnv:
    """Use the current Python environment for analysis.

    No temporary directory is created.
    """
    site_packages = Path(sysconfig.get_path("purelib"))
    return ProvisionedEnv(site_packages=site_packages)


def provision_from_venv(venv_path: Path) -> ProvisionedEnv:
    """Use an existing virtual environment for analysis.

    Args:
        venv_path: Path to a .venv or virtualenv directory.

    Raises:
        FileNotFoundError: If no site-packages directory is found.
    """
    sp = _find_site_packages(venv_path)
    if sp is None:
        msg = f"No site-packages directory found in {venv_path}"
        raise FileNotFoundError(msg)
    return ProvisionedEnv(site_packages=sp)


def provision_temp_env(specs: list[PackageSpec]) -> ProvisionedEnv:
    """Create a temporary virtual environment and install packages.

    Uses uv for fast environment creation and package installation.

    Args:
        specs: Package specifications to install.

    Raises:
        RuntimeError: If uv is not available or installation fails.
    """
    if not check_uv_available():
        msg = (
            "license_audit requires 'uv' to analyze external projects. "
            "Install it with: pip install uv"
        )
        raise RuntimeError(msg)

    tmp_dir = tempfile.TemporaryDirectory(prefix="license_audit_")
    # Safety net: clean up even if context manager is bypassed
    atexit.register(tmp_dir.cleanup)

    venv_path = Path(tmp_dir.name) / ".venv"

    try:
        subprocess.run(
            ["uv", "venv", str(venv_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        if specs:
            python_path = _find_python(venv_path)
            _install_specs(specs, python_path)
    except subprocess.CalledProcessError as e:
        tmp_dir.cleanup()
        msg = (
            f"Failed to provision environment: {e.stderr or e.stdout or str(e)}\n"
            "Check your network connection and that all packages exist on PyPI."
        )
        raise RuntimeError(msg) from e

    sp = _find_site_packages(venv_path)
    if sp is None:
        tmp_dir.cleanup()
        msg = f"No site-packages found in provisioned environment at {venv_path}"
        raise RuntimeError(msg)

    return ProvisionedEnv(site_packages=sp, _tmp_dir=tmp_dir)


def _install_specs(specs: list[PackageSpec], python_path: Path) -> None:
    """Install package specs, falling back to individual installs on failure."""
    base_cmd = [
        "uv",
        "pip",
        "install",
        "--prerelease",
        "allow",
        "--python",
        str(python_path),
    ]
    install_args = [_spec_to_install_arg(s) for s in specs]

    result = subprocess.run(
        [*base_cmd, *install_args],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return

    # Batch install failed -- fall back to installing one-by-one so that
    # unpublished / dev-only versions don't block the entire run.
    logger.debug("Batch install failed, falling back to individual installs")
    for spec in specs:
        arg = _spec_to_install_arg(spec)
        per_pkg = subprocess.run(
            [*base_cmd, arg],
            capture_output=True,
            text=True,
        )
        if per_pkg.returncode != 0:
            # Try again without the version pin, we still get license metadata
            fallback = subprocess.run(
                [*base_cmd, spec.name],
                capture_output=True,
                text=True,
            )
            if fallback.returncode != 0:
                logger.warning(
                    "Could not install '%s', skipping (license info will be unavailable)",
                    arg,
                )
            else:
                logger.warning(
                    "Exact version %s not available; "
                    "installed latest release instead (license may differ)",
                    arg,
                )


def _spec_to_install_arg(spec: PackageSpec) -> str:
    """Convert a PackageSpec to a pip install argument.

    Uses ``name @ url`` for URL/git sources (PEP 508), otherwise falls
    back to name + version constraint for registry packages.
    """
    if spec.source_url:
        return f"{spec.name} @ {spec.source_url}"
    return f"{spec.name}{spec.version_constraint}"


def check_uv_available() -> bool:
    """Check if uv is available on PATH."""
    return shutil.which("uv") is not None


def _find_python(venv_path: Path) -> Path:
    """Find the Python executable in a virtual environment."""
    # Unix
    python = venv_path / "bin" / "python"
    if python.exists():
        return python
    # Windows
    python = venv_path / "Scripts" / "python.exe"
    if python.exists():
        return python
    msg = f"Python executable not found in {venv_path}"
    raise FileNotFoundError(msg)


def _find_site_packages(venv_path: Path) -> Path | None:
    """Find the site-packages directory in a virtual environment."""
    # Unix: .venv/lib/pythonX.Y/site-packages
    lib_dir = venv_path / "lib"
    if lib_dir.is_dir():
        for child in lib_dir.iterdir():
            sp = child / "site-packages"
            if sp.is_dir():
                return sp

    # Windows: .venv/Lib/site-packages
    sp = venv_path / "Lib" / "site-packages"
    if sp.is_dir():
        return sp

    return None


def is_venv_dir(path: Path) -> bool:
    """Check if a directory looks like a virtual environment."""
    if not path.is_dir():
        return False
    # Must have site-packages but NOT be a project root (no pyproject.toml)
    if (path / "pyproject.toml").exists():
        return False
    return _find_site_packages(path) is not None
