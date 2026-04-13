"""Shared utilities for license_audit."""

from __future__ import annotations

from email.parser import HeaderParser
from pathlib import Path
from typing import Any

_header_parser = HeaderParser()


def canonicalize(name: str) -> str:
    """Canonicalize a package name per PEP 503.

    Lowercases the name and replaces hyphens and dots with underscores,
    producing a normalized form suitable for comparison and lookup.
    """
    return name.lower().replace("-", "_").replace(".", "_")


def load_metadata_from_site_packages(
    package_name: str, site_packages: Path
) -> Any | None:
    """Find and parse METADATA for a package in a site-packages directory.

    Looks for a ``*.dist-info/METADATA`` file matching the given package name
    (after PEP 503 canonicalization) and returns the parsed email headers,
    or ``None`` if no matching metadata is found.
    """
    canonical = canonicalize(package_name)

    for dist_info in site_packages.glob("*.dist-info"):
        metadata_file = dist_info / "METADATA"
        if not metadata_file.exists():
            continue
        dir_name = dist_info.name.rsplit(".dist-info", 1)[0]
        parts = dir_name.split("-", 1)
        dist_name = canonicalize(parts[0])
        if dist_name == canonical:
            text = metadata_file.read_text(encoding="utf-8")
            return _header_parser.parsestr(text)

    return None


def get_license_text(package_name: str, site_packages: Path) -> str | None:
    """Read the license file contents for a package from its dist-info directory.

    Checks PEP 639 ``License-File`` metadata entries first, then falls back
    to common license file names (LICENSE, LICENCE, COPYING, NOTICE).

    Returns the concatenated text of all license files found, or ``None``
    if no license files exist.
    """
    canonical = canonicalize(package_name)

    for dist_info in site_packages.glob("*.dist-info"):
        dir_name = dist_info.name.rsplit(".dist-info", 1)[0]
        parts = dir_name.split("-", 1)
        dist_name = canonicalize(parts[0])
        if dist_name != canonical:
            continue

        texts = _read_pep639_license_files(dist_info)
        if not texts:
            texts = _read_common_license_files(dist_info)

        if texts:
            return "\n".join(texts)

    return None


def _read_pep639_license_files(dist_info: Path) -> list[str]:
    """Read license files listed in PEP 639 License-File metadata entries."""
    metadata_file = dist_info / "METADATA"
    if not metadata_file.exists():
        return []

    meta = _header_parser.parsestr(metadata_file.read_text(encoding="utf-8"))
    texts: list[str] = []
    for lf in meta.get_all("License-File") or []:
        # Check both the dist-info root and the licenses/ subdirectory
        # (PEP 639 stores files under licenses/ but the metadata value
        # is the relative filename without the subdirectory prefix).
        for candidate in (dist_info / lf, dist_info / "licenses" / lf):
            if candidate.is_file():
                texts.append(candidate.read_text(encoding="utf-8", errors="replace"))
                break
    return texts


def _read_common_license_files(dist_info: Path) -> list[str]:
    """Read license files matching common naming patterns."""
    texts: list[str] = []
    search_dirs = [dist_info]
    licenses_dir = dist_info / "licenses"
    if licenses_dir.is_dir():
        search_dirs.append(licenses_dir)
    for directory in search_dirs:
        for pattern in ("LICENSE*", "LICENCE*", "COPYING*", "NOTICE*"):
            for path in directory.glob(pattern):
                if path.is_file():
                    texts.append(path.read_text(encoding="utf-8", errors="replace"))
    return texts
