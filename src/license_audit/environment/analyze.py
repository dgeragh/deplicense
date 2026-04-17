"""Analyze a Python environment for dependency licenses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

from license_audit.core.models import DependencyNode, PackageLicense
from license_audit.licenses.detection import detect_license_from_path
from license_audit.util import MetadataReader, canonicalize

_metadata_reader = MetadataReader()


def analyze_environment(
    project_name: str,
    site_packages: Path,
    overrides: dict[str, str] | None = None,
) -> DependencyNode:
    """Build a dependency tree by analyzing an environment's site-packages.

    Recursively walks installed packages starting from the root project,
    reading METADATA files to detect licenses and resolve transitive deps.
    After the walk, any installed packages not reachable from the root
    (e.g. dev dependencies) are included as additional direct dependencies.

    Args:
        project_name: The root project name.
        site_packages: Path to the site-packages directory to analyze.
        overrides: Manual license overrides from config.

    Returns:
        A DependencyNode tree rooted at the project.
    """
    overrides = overrides or {}
    visited: set[str] = set()
    root = _resolve_package(project_name, site_packages, overrides, visited)

    # Discover any installed packages not reachable from the root's METADATA
    # (e.g. dev dependencies, docs tools, test frameworks).
    for name in _discover_installed_packages(site_packages):
        if name not in visited:
            node = _resolve_package(name, site_packages, overrides, visited)
            root.dependencies.append(node)

    return root


def analyze_installed_packages(
    project_name: str,
    site_packages: Path,
    package_names: list[str],
    overrides: dict[str, str] | None = None,
    package_extras: dict[str, frozenset[str]] | None = None,
) -> DependencyNode:
    """Build a dependency tree from a known list of top-level packages.

    Used when the root project is not installed in the environment (e.g.,
    when analyzing via a temp env created from a source file). Each package
    in the list becomes a direct dependency of a synthetic root node, and
    transitive deps are resolved from their METADATA.

    Args:
        project_name: Name for the synthetic root node.
        site_packages: Path to the site-packages directory.
        package_names: Top-level package names to analyze.
        overrides: Manual license overrides from config.
        package_extras: Mapping of package name to requested extras.

    Returns:
        A DependencyNode tree with a synthetic root and all packages as deps.
    """
    overrides = overrides or {}
    package_extras = package_extras or {}
    visited: set[str] = set()
    root_pkg = PackageLicense(name=canonicalize(project_name), version="0.0.0")
    deps: list[DependencyNode] = []

    for name in package_names:
        extras = package_extras.get(name, frozenset())
        node = _resolve_package(name, site_packages, overrides, visited, extras)
        deps.append(node)

    return DependencyNode(package=root_pkg, dependencies=deps)


def _resolve_package(
    name: str,
    site_packages: Path,
    overrides: dict[str, str],
    visited: set[str],
    extras: frozenset[str] = frozenset(),
) -> DependencyNode:
    """Recursively resolve a package and its dependencies."""
    canonical = canonicalize(name)
    version = _get_version_from_path(canonical, site_packages)
    license_expr, source = detect_license_from_path(canonical, site_packages, overrides)

    pkg = PackageLicense(
        name=canonical,
        version=version,
        license_expression=license_expr,
        license_source=source,
    )

    if canonical in visited:
        return DependencyNode(package=pkg)

    visited.add(canonical)
    deps: list[DependencyNode] = []

    requires = _get_requires_dist_from_path(canonical, site_packages)
    for req_str in requires:
        try:
            req = Requirement(req_str)
        except InvalidRequirement:
            continue

        # Skip deps whose markers don't apply in the current environment.
        # Evaluate with each requested extra so that optional dependencies
        # gated by ``extra == "..."`` markers are included.
        if req.marker and not _marker_matches(req.marker, extras):
            continue

        dep_extras = frozenset(req.extras) if req.extras else frozenset()
        dep_node = _resolve_package(
            req.name, site_packages, overrides, visited, dep_extras
        )
        deps.append(dep_node)

    return DependencyNode(package=pkg, dependencies=deps)


def _marker_matches(marker: Any, extras: frozenset[str]) -> bool:
    """Check if a marker matches the current environment with the given extras."""
    # First check without any extras (covers non-extra markers)
    if marker.evaluate():
        return True
    # Then check with each requested extra
    return any(marker.evaluate({"extra": extra}) for extra in extras)


def _discover_installed_packages(site_packages: Path) -> list[str]:
    """Return canonicalized names of all packages installed in site-packages."""
    names: list[str] = []
    for dist_info in site_packages.glob("*.dist-info"):
        dir_name = dist_info.name.rsplit(".dist-info", 1)[0]
        parts = dir_name.split("-", 1)
        names.append(canonicalize(parts[0]))
    return names


def _get_version_from_path(package_name: str, site_packages: Path) -> str:
    """Get a package's version from its METADATA in site-packages."""
    meta = _load_metadata(package_name, site_packages)
    if meta is not None:
        version = meta.get("Version")
        if version:
            return str(version)
    return "unknown"


def _get_requires_dist_from_path(package_name: str, site_packages: Path) -> list[str]:
    """Get Requires-Dist entries from a package's METADATA in site-packages."""
    meta = _load_metadata(package_name, site_packages)
    if meta is None:
        return []
    return meta.get_all("Requires-Dist") or []


def _load_metadata(package_name: str, site_packages: Path) -> Any | None:
    """Find and parse METADATA for a package in site-packages."""
    return _metadata_reader.read_metadata(package_name, site_packages)
