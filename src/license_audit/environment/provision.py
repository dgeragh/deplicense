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
            atexit.unregister(self._tmp_dir.cleanup)
            self._tmp_dir.cleanup()
            self._tmp_dir = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.cleanup()


class EnvironmentProvisioner:
    """Create / attach to Python environments used for license inspection."""

    INSTALL_TIMEOUT_SECONDS: int = 30

    def current(self) -> ProvisionedEnv:
        """Analyze the current Python environment; no temp dir created."""
        site_packages = Path(sysconfig.get_path("purelib"))
        return ProvisionedEnv(site_packages=site_packages)

    def from_venv(self, venv_path: Path) -> ProvisionedEnv:
        """Attach to an existing virtualenv.

        Raises ``FileNotFoundError`` if no site-packages dir can be found.
        """
        sp = self._find_site_packages(venv_path)
        if sp is None:
            msg = f"No site-packages directory found in {venv_path}"
            raise FileNotFoundError(msg)
        return ProvisionedEnv(site_packages=sp)

    def temp(self, specs: list[PackageSpec]) -> ProvisionedEnv:
        """Create a temp virtualenv via ``uv`` and install ``specs``.

        The temp directory's cleanup is registered with ``atexit`` as a
        safety net before any further work runs, so a crash or exception
        in venv creation cannot leak the directory.
        """
        if not self.check_uv_available():
            msg = (
                "license_audit requires 'uv' to analyze external projects. "
                "Install it with: pip install uv"
            )
            raise RuntimeError(msg)

        tmp_dir = tempfile.TemporaryDirectory(prefix="license_audit_")
        atexit.register(tmp_dir.cleanup)

        try:
            venv_path = Path(tmp_dir.name) / ".venv"
            subprocess.run(
                ["uv", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True,
            )

            if specs:
                python_path = self._find_python(venv_path)
                self._install_specs(specs, python_path)

            sp = self._find_site_packages(venv_path)
        except subprocess.CalledProcessError as e:
            atexit.unregister(tmp_dir.cleanup)
            tmp_dir.cleanup()
            msg = (
                f"Failed to provision environment: {e.stderr or e.stdout or str(e)}\n"
                "Check your network connection and that all packages exist on PyPI."
            )
            raise RuntimeError(msg) from e
        except BaseException:
            atexit.unregister(tmp_dir.cleanup)
            tmp_dir.cleanup()
            raise

        if sp is None:
            atexit.unregister(tmp_dir.cleanup)
            tmp_dir.cleanup()
            msg = f"No site-packages found in provisioned environment at {venv_path}"
            raise RuntimeError(msg)

        return ProvisionedEnv(site_packages=sp, _tmp_dir=tmp_dir)

    def check_uv_available(self) -> bool:
        """Return True if ``uv`` is on PATH."""
        return shutil.which("uv") is not None

    def is_venv_dir(self, path: Path) -> bool:
        """Return True if ``path`` looks like a virtualenv (site-packages + no pyproject)."""
        if not path.is_dir():
            return False
        if (path / "pyproject.toml").exists():
            return False
        return self._find_site_packages(path) is not None

    def _install_specs(self, specs: list[PackageSpec], python_path: Path) -> None:
        base_cmd = [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "--python",
            str(python_path),
        ]
        install_args = [self._spec_to_install_arg(s) for s in specs]

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
            arg = self._spec_to_install_arg(spec)
            per_pkg = subprocess.run([*base_cmd, arg], capture_output=True, text=True)
            if per_pkg.returncode != 0:
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

    @staticmethod
    def _spec_to_install_arg(spec: PackageSpec) -> str:
        """Convert a ``PackageSpec`` to a ``uv pip install`` positional arg."""
        if spec.source_url:
            return f"{spec.name} @ {spec.source_url}"
        return f"{spec.name}{spec.version_constraint}"

    @staticmethod
    def _find_python(venv_path: Path) -> Path:
        """Return the Python binary inside a virtualenv."""
        python = venv_path / "bin" / "python"
        if python.exists():
            return python
        python = venv_path / "Scripts" / "python.exe"
        if python.exists():
            return python
        msg = f"Python executable not found in {venv_path}"
        raise FileNotFoundError(msg)

    @staticmethod
    def _find_site_packages(venv_path: Path) -> Path | None:
        """Return the site-packages dir inside a virtualenv, or ``None``."""
        lib_dir = venv_path / "lib"
        if lib_dir.is_dir():
            for child in lib_dir.iterdir():
                sp = child / "site-packages"
                if sp.is_dir():
                    return sp

        sp = venv_path / "Lib" / "site-packages"
        if sp.is_dir():
            return sp

        return None
