"""AND/OR-aware evaluation of SPDX license expressions."""

from __future__ import annotations

from typing import Any

from license_expression import AND, OR, LicenseSymbol

from license_audit.core.classifier import LicenseClassifier
from license_audit.core.models import CATEGORY_RANK, LicenseCategory
from license_audit.licenses.spdx import SpdxNormalizer


class ExpressionEvaluator:
    """Evaluates SPDX expressions with AND/OR semantics.

    `A AND B` requires complying with both, so the effective constraint
    is the most restrictive component. `A OR B` lets the consumer pick
    one, so the effective constraint is the most permissive alternative.
    """

    def __init__(
        self,
        classifier: LicenseClassifier | None = None,
        normalizer: SpdxNormalizer | None = None,
    ) -> None:
        self._classifier = classifier or LicenseClassifier()
        self._normalizer = normalizer or SpdxNormalizer()

    def alternatives(self, expr: str) -> list[list[str]]:
        """Distribute AND over OR into a list of jointly-required id sets.

        `A AND (B OR C)` becomes `[[A, B], [A, C]]`. Returns `[[]]` when
        the expression can't be parsed.
        """
        parsed = self._normalizer.parse_expression(expr)
        if parsed is None:
            return [[]]
        return self._walk_alternatives(parsed)

    def required_ids(self, expr: str) -> list[str]:
        """Ids the project must comply with after resolving every OR.

        Picks the alternative whose worst-case license has the lowest
        permissiveness rank.
        """
        non_empty = [alt for alt in self.alternatives(expr) if alt]
        if not non_empty:
            return []
        best = min(non_empty, key=self._alt_rank)
        return list(dict.fromkeys(best))

    def classify(self, expr: str) -> LicenseCategory:
        """Category of the best-case alternative for `expr`."""
        non_empty = [alt for alt in self.alternatives(expr) if alt]
        if not non_empty:
            return self._classifier.classify(expr)
        best = min(non_empty, key=self._alt_rank)
        return max(
            (self._classifier.classify(lic) for lic in best),
            key=lambda c: CATEGORY_RANK.get(c, 5),
        )

    def passes_denied_allowed(
        self,
        expr: str,
        denied: set[str],
        allowed: set[str],
    ) -> bool:
        """True if at least one alternative avoids `denied` and fits `allowed`.

        `denied` and `allowed` must be lower-cased SPDX ids. An empty
        `allowed` set means no allowlist constraint.
        """
        for alt in self.alternatives(expr):
            if not alt:
                continue
            lowered = [lic.lower() for lic in alt]
            if any(lic in denied for lic in lowered):
                continue
            if allowed and any(lic not in allowed for lic in lowered):
                continue
            return True
        return False

    def _alt_rank(self, alt: list[str]) -> int:
        return max(
            (CATEGORY_RANK.get(self._classifier.classify(lic), 5) for lic in alt),
            default=CATEGORY_RANK[LicenseCategory.UNKNOWN],
        )

    def _walk_alternatives(self, node: Any) -> list[list[str]]:
        if isinstance(node, LicenseSymbol):
            return [[self._normalize_key(str(node.key))]]
        if isinstance(node, OR):
            result: list[list[str]] = []
            for arg in node.args:
                result.extend(self._walk_alternatives(arg))
            return result
        if isinstance(node, AND):
            # Cartesian product across children: each AND child contributes
            # one branch per alternative.
            combined: list[list[str]] = [[]]
            for arg in node.args:
                child = self._walk_alternatives(arg)
                combined = [parent + branch for parent in combined for branch in child]
            return combined
        return [[]]

    @staticmethod
    def _normalize_key(key: str) -> str:
        return SpdxNormalizer.DEPRECATED_SPDX.get(key, key)
