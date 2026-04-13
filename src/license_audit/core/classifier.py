"""License classification using OSADL copyleft data."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from license_audit._data import load_data_file
from license_audit.core.models import LicenseCategory

_COPYLEFT_MAP: dict[str, LicenseCategory] = {
    "Yes": LicenseCategory.STRONG_COPYLEFT,
    "Yes (restricted)": LicenseCategory.WEAK_COPYLEFT,
    "No": LicenseCategory.PERMISSIVE,
    "Questionable": LicenseCategory.UNKNOWN,
}

# Network copyleft licenses (AGPL family)
_NETWORK_COPYLEFT = frozenset({
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "AGPL-1.0-only",
    "AGPL-1.0-or-later",
})


def _load_copyleft() -> dict[str, str]:
    """Load the OSADL copyleft classifications from bundled data."""
    raw: dict[str, Any] = json.loads(load_data_file("copyleft.json"))
    copyleft_data = raw.get("copyleft", {})
    if not isinstance(copyleft_data, dict):
        return {}
    return {k: v for k, v in copyleft_data.items() if isinstance(v, str)}


@lru_cache(maxsize=1)
def get_copyleft_data() -> dict[str, str]:
    """Get the cached copyleft classification data."""
    return _load_copyleft()


def classify(spdx_id: str) -> LicenseCategory:
    """Classify a license by its copyleft nature.

    Args:
        spdx_id: An SPDX license identifier (e.g., "MIT", "GPL-3.0-only").

    Returns:
        The license category.
    """
    if spdx_id in _NETWORK_COPYLEFT:
        return LicenseCategory.NETWORK_COPYLEFT

    copyleft_data = get_copyleft_data()
    raw_value = copyleft_data.get(spdx_id)
    if raw_value is not None:
        return _COPYLEFT_MAP.get(raw_value, LicenseCategory.UNKNOWN)

    return LicenseCategory.UNKNOWN
