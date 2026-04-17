"""License detection from package metadata."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from pathlib import Path
from typing import Any

from license_audit.core.models import UNKNOWN_LICENSE, LicenseSource
from license_audit.licenses.spdx import SpdxNormalizer
from license_audit.util import load_metadata_from_site_packages

_normalizer = SpdxNormalizer()


def detect_license(
    package_name: str,
    overrides: dict[str, str] | None = None,
) -> tuple[str, LicenseSource]:
    """Detect the license for a package from the current environment.

    Detection order:
    1. User overrides
    2. PEP 639 License-Expression metadata field
    3. License metadata field (normalized)
    4. Trove classifiers
    5. UNKNOWN
    """
    if overrides and package_name in overrides:
        return overrides[package_name], LicenseSource.OVERRIDE

    try:
        meta = importlib_metadata.metadata(package_name)
    except importlib_metadata.PackageNotFoundError:
        return UNKNOWN_LICENSE, LicenseSource.UNKNOWN

    return _detect_from_metadata(meta)


def detect_license_from_path(
    package_name: str,
    site_packages: Path,
    overrides: dict[str, str] | None = None,
) -> tuple[str, LicenseSource]:
    """Detect the license for a package by reading from a site-packages directory.

    Useful when analyzing a project whose dependencies are installed in a
    different .venv than the one running license_audit.
    """
    if overrides and package_name in overrides:
        return overrides[package_name], LicenseSource.OVERRIDE

    meta = load_metadata_from_site_packages(package_name, site_packages)
    if meta is None:
        return UNKNOWN_LICENSE, LicenseSource.UNKNOWN

    return _detect_from_metadata(meta)


def _detect_from_metadata(meta: Any) -> tuple[str, LicenseSource]:
    """Extract license from package metadata fields."""
    # PEP 639 License-Expression
    result = _try_pep639(meta)
    if result:
        return result

    # License metadata field
    result = _try_license_field(meta)
    if result:
        return result

    # Trove classifiers
    result = _try_classifiers(meta)
    if result:
        return result

    return "UNKNOWN", LicenseSource.UNKNOWN


def _try_pep639(meta: Any) -> tuple[str, LicenseSource] | None:
    license_expr = meta.get("License-Expression")
    if license_expr and license_expr.strip().upper() != UNKNOWN_LICENSE:
        normalized = _normalizer.normalize(license_expr)
        if normalized != UNKNOWN_LICENSE:
            return normalized, LicenseSource.PEP639
    return None


def _try_license_field(meta: Any) -> tuple[str, LicenseSource] | None:
    license_field = meta.get("License")
    if license_field and license_field.strip().upper() not in ("UNKNOWN", "", "NONE"):
        normalized = _normalizer.normalize(license_field)
        if normalized != UNKNOWN_LICENSE:
            return normalized, LicenseSource.METADATA
    return None


def _try_classifiers(meta: Any) -> tuple[str, LicenseSource] | None:
    classifiers = meta.get_all("Classifier") or []
    license_classifiers = [c for c in classifiers if c.startswith("License ::")]
    spdx_from_classifiers: list[str] = []
    for cls in license_classifiers:
        spdx = _normalizer.normalize_classifier(cls)
        if spdx:
            spdx_from_classifiers.append(spdx)

    if len(spdx_from_classifiers) == 1:
        return spdx_from_classifiers[0], LicenseSource.CLASSIFIER
    if len(spdx_from_classifiers) > 1:
        expr = " OR ".join(sorted(set(spdx_from_classifiers)))
        return expr, LicenseSource.CLASSIFIER
    return None
