"""Parse dependencies from a pyproject.toml file."""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from license_audit.sources.base import PackageSpec
from license_audit.util import canonicalize


class PyprojectSource:
    """Parse all dependencies from a pyproject.toml to extract package specs.

    Covers:
    - ``[project.dependencies]``
    - ``[project.optional-dependencies.*]`` (extras)
    - ``[dependency-groups.*]`` (PEP 735)
    - ``[tool.uv.dev-dependencies]`` (uv-specific legacy)
    """

    def __init__(self, pyproject_path: Path, groups: list[str] | None = None) -> None:
        self._path = pyproject_path
        self._groups = groups

    def _include(self, selector: str) -> bool:
        """Return True if the given group selector should be included."""
        return self._groups is None or selector in self._groups

    def parse(self) -> list[PackageSpec]:
        """Parse pyproject.toml dependencies and return package specs."""
        if not self._path.exists():
            msg = f"pyproject.toml not found at {self._path}"
            raise FileNotFoundError(msg)

        with open(self._path, "rb") as f:
            data = tomllib.load(f)

        raw = self._collect_raw_deps(data)
        return _parse_requirements(raw)

    def _collect_raw_deps(self, data: dict[str, object]) -> list[str]:
        """Collect raw dependency strings from all selected groups."""
        raw: list[str] = []

        # [project.dependencies]
        if self._include("main"):
            project = data.get("project", {})
            raw.extend(
                _as_str_list(
                    project.get("dependencies") if isinstance(project, dict) else None
                )
            )

        # [project.optional-dependencies.*]
        project = data.get("project", {})
        opt_deps = (
            project.get("optional-dependencies", {})
            if isinstance(project, dict)
            else {}
        )
        if isinstance(opt_deps, dict):
            for name, group_deps in opt_deps.items():
                if self._include(f"optional:{name}"):
                    raw.extend(_as_str_list(group_deps))

        # [dependency-groups.*] (PEP 735)
        dep_groups = data.get("dependency-groups", {})
        if isinstance(dep_groups, dict):
            for name, group_deps in dep_groups.items():
                if self._include(f"group:{name}"):
                    raw.extend(_as_str_list(group_deps))

        # [tool.uv.dev-dependencies]
        if self._include("dev"):
            tool = data.get("tool", {})
            uv = tool.get("uv", {}) if isinstance(tool, dict) else {}
            uv_dev = uv.get("dev-dependencies") if isinstance(uv, dict) else None
            raw.extend(_as_str_list(uv_dev))

        return raw


def _parse_requirements(raw: list[str]) -> list[PackageSpec]:
    """Parse raw requirement strings into deduplicated PackageSpecs."""
    seen: set[str] = set()
    specs: list[PackageSpec] = []
    for dep_str in raw:
        try:
            req = Requirement(dep_str)
        except InvalidRequirement:
            continue

        name = canonicalize(req.name)
        if name in seen:
            continue
        seen.add(name)

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


def _as_str_list(value: object) -> list[str]:
    """Coerce a value to a list of strings, filtering out non-string items."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
