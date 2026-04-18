"""Recommend outbound licenses compatible with a set of dependencies."""

from __future__ import annotations

from license_expression import OR

from license_audit.core.classifier import LicenseClassifier
from license_audit.core.compatibility import CompatibilityMatrix
from license_audit.core.models import CATEGORY_RANK, UNKNOWN_LICENSE
from license_audit.licenses.spdx import SpdxNormalizer


class LicenseRecommender:
    """Picks compatible outbound licenses ranked by permissiveness."""

    PREFERRED_PERMISSIVE: list[str] = [
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "0BSD",
        "Unlicense",
    ]

    def __init__(
        self,
        matrix: CompatibilityMatrix | None = None,
        classifier: LicenseClassifier | None = None,
        normalizer: SpdxNormalizer | None = None,
    ) -> None:
        self._matrix = matrix or CompatibilityMatrix()
        self._classifier = classifier or LicenseClassifier()
        self._normalizer = normalizer or SpdxNormalizer(matrix=self._matrix)

    def recommend(self, dependency_licenses: list[str]) -> list[str]:
        """Compatible outbound licenses, most permissive first."""
        resolved = self.resolve_inbound(dependency_licenses)
        if not resolved:
            return self.PREFERRED_PERMISSIVE.copy()

        compatible = self._matrix.find_compatible_outbound(resolved)
        return sorted(
            compatible,
            key=lambda lic: (
                CATEGORY_RANK.get(self._classifier.classify(lic), 5),
                lic,
            ),
        )

    def find_minimum(self, dependency_licenses: list[str]) -> str | None:
        """The single most permissive compatible outbound license, or None."""
        recommended = self.recommend(dependency_licenses)
        if not recommended:
            return None
        return recommended[0]

    def resolve_inbound(self, expressions: list[str]) -> list[str]:
        """Flatten SPDX expressions into a deduplicated list of licenses.

        OR reduces to the most permissive branch, AND keeps every component,
        and UNKNOWN is dropped. OR/AND is detected via the parsed AST so
        whitespace and casing in the raw text don't matter.
        """
        resolved: set[str] = set()
        for expr in expressions:
            if expr == UNKNOWN_LICENSE:
                continue

            simple = self._normalizer.get_simple_licenses(expr)
            if len(simple) == 1:
                resolved.add(simple[0])
                continue

            parsed = self._normalizer.parse_expression(expr)
            if isinstance(parsed, OR):
                best = min(
                    simple,
                    key=lambda lic: CATEGORY_RANK.get(
                        self._classifier.classify(lic),
                        5,
                    ),
                )
                resolved.add(best)
            else:
                resolved.update(simple)

        return list(resolved)
