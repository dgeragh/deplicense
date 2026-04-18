"""Build the right Source for a given dependency file."""

from __future__ import annotations

from pathlib import Path

from license_audit.sources.base import Source
from license_audit.sources.pyproject import PyprojectSource
from license_audit.sources.requirements import RequirementsSource
from license_audit.sources.uv_lock import UvLockSource


class SourceFactory:
    """Picks the right Source subclass for a dependency file."""

    # Search order for auto-detection: first hit wins.
    PROJECT_FILES: tuple[str, ...] = ("uv.lock", "requirements.txt", "pyproject.toml")

    def create(self, path: Path, groups: list[str] | None = None) -> Source:
        """Instantiate a Source for `path`, or raise ValueError if unrecognized."""
        name = path.name.lower()
        if name == "uv.lock":
            return UvLockSource(path, groups=groups)
        if self._is_requirements(name):
            return RequirementsSource(path, groups=groups)
        if name == "pyproject.toml":
            return PyprojectSource(path, groups=groups)
        msg = f"Unrecognized dependency file: {path.name}"
        raise ValueError(msg)

    def validate(self, path: Path) -> None:
        """Raise ValueError if `path` isn't a recognized dependency file."""
        name = path.name.lower()
        if name in ("uv.lock", "pyproject.toml"):
            return
        if self._is_requirements(name):
            return
        msg = f"Unrecognized dependency file: {path.name}"
        raise ValueError(msg)

    def detect_in_project_dir(self, project_dir: Path) -> Path | None:
        """First recognized dependency file in `project_dir`, or None."""
        for filename in self.PROJECT_FILES:
            candidate = project_dir / filename
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _is_requirements(name: str) -> bool:
        return name.startswith("requirements") and name.endswith(".txt")
