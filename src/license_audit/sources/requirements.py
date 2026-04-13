"""Parse dependencies from a requirements.txt file."""

from __future__ import annotations

from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from license_audit.sources.base import PackageSpec
from license_audit.util import canonicalize


class RequirementsSource:
    """Parse a requirements.txt file to extract package specs."""

    def __init__(
        self, requirements_path: Path, groups: list[str] | None = None
    ) -> None:
        self._path = requirements_path
        # groups is accepted for API consistency but ignored (flat format).

    def parse(self) -> list[PackageSpec]:
        """Parse requirements.txt and return package specs."""
        if not self._path.exists():
            msg = f"requirements.txt not found at {self._path}"
            raise FileNotFoundError(msg)

        lines = self._path.read_text().splitlines()
        specs: list[PackageSpec] = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            try:
                req = Requirement(line)
            except InvalidRequirement:
                continue

            name = canonicalize(req.name)
            constraint = str(req.specifier) if req.specifier else ""
            source_url = req.url or ""
            extras = frozenset(req.extras) if req.extras else frozenset()
            specs.append(
                PackageSpec(
                    name=name,
                    version_constraint=constraint,
                    source_url=source_url,
                    extras=extras,
                )
            )

        return specs
