"""Tests for SPDX normalization."""

from license_audit.licenses.spdx import (
    get_simple_licenses,
    normalize,
    normalize_classifier,
    parse_expression,
)


class TestNormalize:
    def test_valid_spdx(self) -> None:
        assert normalize("MIT") == "MIT"

    def test_apache_alias(self) -> None:
        assert normalize("Apache Software License") == "Apache-2.0"

    def test_bsd_alias(self) -> None:
        assert normalize("BSD License") == "BSD-3-Clause"

    def test_case_insensitive(self) -> None:
        assert normalize("mit license") == "MIT"
        assert normalize("MIT LICENSE") == "MIT"

    def test_unknown(self) -> None:
        assert normalize("UNKNOWN") == "UNKNOWN"
        assert normalize("") == "UNKNOWN"
        assert normalize("   ") == "UNKNOWN"

    def test_compound_expression(self) -> None:
        result = normalize("MIT OR Apache-2.0")
        assert "MIT" in result
        assert "Apache-2.0" in result

    def test_gpl_aliases(self) -> None:
        assert normalize("GPLv3") == "GPL-3.0-only"
        assert normalize("GNU GPL v2") == "GPL-2.0-only"

    def test_deprecated_spdx_normalized(self) -> None:
        assert normalize("GPL-2.0") == "GPL-2.0-only"
        assert normalize("LGPL-3.0") == "LGPL-3.0-only"
        assert normalize("AGPL-3.0") == "AGPL-3.0-only"

    def test_nonspdx_string_returns_unknown(self) -> None:
        assert normalize("Dual License") == "UNKNOWN"
        assert normalize("Custom License v2") == "UNKNOWN"

    def test_none_value(self) -> None:
        assert normalize("NONE") == "UNKNOWN"


class TestNormalizeClassifier:
    def test_mit(self) -> None:
        result = normalize_classifier("License :: OSI Approved :: MIT License")
        assert result == "MIT"

    def test_apache(self) -> None:
        result = normalize_classifier(
            "License :: OSI Approved :: Apache Software License"
        )
        assert result == "Apache-2.0"

    def test_unknown_classifier(self) -> None:
        result = normalize_classifier("License :: Something Unknown")
        assert result is None


class TestParseExpression:
    def test_simple(self) -> None:
        result = parse_expression("MIT")
        assert result is not None

    def test_compound(self) -> None:
        result = parse_expression("MIT OR Apache-2.0")
        assert result is not None

    def test_invalid(self) -> None:
        result = parse_expression("not a valid expression!!!")
        assert result is None


class TestGetSimpleLicenses:
    def test_single(self) -> None:
        result = get_simple_licenses("MIT")
        assert result == ["MIT"]

    def test_or_expression(self) -> None:
        result = get_simple_licenses("MIT OR Apache-2.0")
        assert "MIT" in result
        assert "Apache-2.0" in result

    def test_unparseable(self) -> None:
        result = get_simple_licenses("garbage!!!")
        assert result == ["garbage!!!"]
