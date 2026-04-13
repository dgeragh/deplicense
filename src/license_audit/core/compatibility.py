"""License compatibility engine using the OSADL matrix."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from license_audit._data import load_data_file
from license_audit.core.models import CompatibilityResult, Verdict

_VERDICT_MAP: dict[str, Verdict] = {
    "Yes": Verdict.COMPATIBLE,
    "No": Verdict.INCOMPATIBLE,
    "Unknown": Verdict.UNKNOWN,
    "Check dependency": Verdict.CHECK_DEPENDENCY,
    "Same": Verdict.SAME,
}

_COMPATIBLE_VERDICTS = {"Yes", "Same", "Check dependency"}


def _load_matrix() -> dict[str, dict[str, str]]:
    """Load the OSADL compatibility matrix from bundled data."""
    raw: dict[str, Any] = json.loads(load_data_file("osadl_matrix.json"))
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


@lru_cache(maxsize=1)
def get_matrix() -> dict[str, dict[str, str]]:
    """Get the cached OSADL compatibility matrix."""
    return _load_matrix()


def _raw_verdict(outbound: str, inbound: str) -> str:
    """Look up the raw OSADL verdict.

    The OSADL matrix uses matrix[outbound][inbound]:
    - outbound = the license of the project (row)
    - inbound = the license of the dependency (column)

    Returns "Yes" if the project (outbound) can use code under the dependency
    license (inbound).
    """
    matrix = get_matrix()
    row = matrix.get(outbound)
    if row is None:
        return "Unknown"
    return row.get(inbound, "Unknown")


def is_compatible(inbound: str, outbound: str) -> CompatibilityResult:
    """Check if a dependency licensed under `inbound` can be used in a project licensed `outbound`.

    Looks up matrix[outbound][inbound] in the OSADL matrix.
    """
    raw = _raw_verdict(outbound, inbound)
    verdict = _VERDICT_MAP.get(raw, Verdict.UNKNOWN)
    return CompatibilityResult(inbound=inbound, outbound=outbound, verdict=verdict)


def known_licenses() -> list[str]:
    """Return the list of licenses known to the OSADL matrix."""
    return list(get_matrix().keys())


def find_compatible_outbound(inbound_licenses: list[str]) -> list[str]:
    """Given a set of dependency (inbound) licenses, find all valid outbound licenses.

    An outbound license is valid if every inbound license is compatible with it
    (verdict is Yes, Same, or Check dependency).

    Inbound licenses not present in the OSADL matrix are skipped -- they
    cannot be evaluated and are surfaced separately as UNKNOWN.
    """
    matrix = get_matrix()
    all_outbound = known_licenses()

    # Only evaluate inbound licenses the matrix can actually answer for.
    # Licenses absent from the OSADL matrix cannot block recommendations;
    # they are surfaced separately as UNKNOWN in the report.
    evaluable = [lic for lic in inbound_licenses if lic in matrix]

    if not evaluable:
        # No evaluable constraints -- every outbound license is valid
        return list(all_outbound)

    compatible: list[str] = []
    for outbound in all_outbound:
        if all(
            _raw_verdict(outbound, inbound) in _COMPATIBLE_VERDICTS
            for inbound in evaluable
        ):
            compatible.append(outbound)
    return compatible


def find_incompatible_pairs(
    licenses: list[str],
) -> list[CompatibilityResult]:
    """Find pairs of licenses in the dependency set that conflict with each other.

    Two licenses A and B conflict if no outbound license in the OSADL matrix
    is compatible with both as inbound simultaneously.

    Licenses not present in the matrix are skipped -- they cannot be
    evaluated and are surfaced separately as UNKNOWN.
    """
    matrix = get_matrix()
    # Only evaluate licenses the matrix can actually answer for.
    # The matrix is symmetric, so checking row keys covers column keys too.
    evaluable = [lic for lic in licenses if lic in matrix]

    results: list[CompatibilityResult] = []
    all_outbound = list(matrix.keys())

    for i, lic_a in enumerate(evaluable):
        for lic_b in evaluable[i + 1 :]:
            # Check whether any outbound license can accommodate both
            has_common = any(
                _raw_verdict(outbound, lic_a) in _COMPATIBLE_VERDICTS
                and _raw_verdict(outbound, lic_b) in _COMPATIBLE_VERDICTS
                for outbound in all_outbound
            )
            if not has_common:
                results.append(
                    CompatibilityResult(
                        inbound=lic_a,
                        outbound=lic_b,
                        verdict=Verdict.INCOMPATIBLE,
                    )
                )
    return results
