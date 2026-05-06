"""License detection from package metadata."""

from __future__ import annotations

from email.message import Message

from license_audit.core.models import UNKNOWN_LICENSE, LicenseSource
from license_audit.licenses.spdx import SpdxNormalizer
from license_audit.util import MetadataReader

_normalizer = SpdxNormalizer()


def detect_license(
    package_name: str,
    reader: MetadataReader,
    overrides: dict[str, str] | None = None,
) -> tuple[str, LicenseSource]:
    """Detect a package's license.

    Detection order:
    1. User overrides
    2. PEP 639 License-Expression metadata field
    3. License metadata field (normalized)
    4. Trove classifiers
    5. UNKNOWN
    """
    if overrides and package_name in overrides:
        return overrides[package_name], LicenseSource.OVERRIDE

    meta = reader.read_metadata(package_name)
    if meta is None:
        return UNKNOWN_LICENSE, LicenseSource.UNKNOWN

    return _detect_from_metadata(meta)


def _detect_from_metadata(meta: Message) -> tuple[str, LicenseSource]:
    """Extract license from package metadata fields."""
    return (
        _try_pep639(meta)
        or _try_license_field(meta)
        or _try_classifiers(meta)
        or (UNKNOWN_LICENSE, LicenseSource.UNKNOWN)
    )


def _try_pep639(meta: Message) -> tuple[str, LicenseSource] | None:
    license_expr = meta.get("License-Expression")
    if license_expr and license_expr.strip().upper() != UNKNOWN_LICENSE:
        normalized = _normalizer.normalize(license_expr)
        if normalized != UNKNOWN_LICENSE:
            return normalized, LicenseSource.PEP639
    return None


def _try_license_field(meta: Message) -> tuple[str, LicenseSource] | None:
    license_field = meta.get("License")
    if license_field and license_field.strip().upper() not in ("UNKNOWN", "", "NONE"):
        normalized = _normalizer.normalize(license_field)
        if normalized != UNKNOWN_LICENSE:
            return normalized, LicenseSource.METADATA
    return None


def _try_classifiers(meta: Message) -> tuple[str, LicenseSource] | None:
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
