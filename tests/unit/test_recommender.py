"""Tests for the license recommender."""

from license_audit.core.recommender import find_minimum_license, recommend_licenses


class TestRecommendLicenses:
    def test_permissive_deps(self) -> None:
        result = recommend_licenses(["MIT", "Apache-2.0", "BSD-3-Clause"])
        assert len(result) > 0
        # All permissive should allow many outbound options
        assert "MIT" in result

    def test_gpl_dep_restricts(self) -> None:
        result = recommend_licenses(["MIT", "GPL-3.0-only"])
        # GPL restricts: MIT should not be valid outbound
        assert "MIT" not in result
        assert "GPL-3.0-only" in result

    def test_empty_deps(self) -> None:
        result = recommend_licenses([])
        assert len(result) > 0

    def test_unknown_skipped(self) -> None:
        result = recommend_licenses(["MIT", "UNKNOWN"])
        assert len(result) > 0

    def test_or_expression(self) -> None:
        result = recommend_licenses(["MIT OR GPL-3.0-only"])
        # Should pick MIT (most permissive) from the OR
        assert "MIT" in result

    def test_and_expression(self) -> None:
        """AND expressions should include all components."""
        result = recommend_licenses(["MIT AND BSD-3-Clause"])
        assert len(result) > 0
        # Both MIT and BSD-3-Clause are permissive, so MIT should be valid
        assert "MIT" in result


class TestFindMinimumLicense:
    def test_permissive(self) -> None:
        result = find_minimum_license(["MIT", "BSD-3-Clause"])
        assert result is not None

    def test_gpl(self) -> None:
        result = find_minimum_license(["MIT", "GPL-3.0-only"])
        assert result is not None
        # Should be a copyleft-compatible license
        assert result != "MIT"

    def test_empty(self) -> None:
        result = find_minimum_license([])
        assert result is not None
