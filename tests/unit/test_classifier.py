"""Tests for license classifier."""

from license_audit.core.classifier import classify, get_copyleft_data
from license_audit.core.models import LicenseCategory


class TestClassify:
    def test_mit_is_permissive(self) -> None:
        assert classify("MIT") == LicenseCategory.PERMISSIVE

    def test_apache_is_permissive(self) -> None:
        assert classify("Apache-2.0") == LicenseCategory.PERMISSIVE

    def test_bsd3_is_permissive(self) -> None:
        assert classify("BSD-3-Clause") == LicenseCategory.PERMISSIVE

    def test_gpl3_is_strong_copyleft(self) -> None:
        assert classify("GPL-3.0-only") == LicenseCategory.STRONG_COPYLEFT

    def test_lgpl_is_weak_copyleft(self) -> None:
        assert classify("LGPL-2.1-only") == LicenseCategory.WEAK_COPYLEFT

    def test_agpl_is_network_copyleft(self) -> None:
        assert classify("AGPL-3.0-only") == LicenseCategory.NETWORK_COPYLEFT

    def test_unknown_license(self) -> None:
        assert classify("NONEXISTENT") == LicenseCategory.UNKNOWN


class TestGetCopyleftData:
    def test_loads_data(self) -> None:
        data = get_copyleft_data()
        assert isinstance(data, dict)
        assert len(data) > 50
        assert "MIT" in data
