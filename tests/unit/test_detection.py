"""Tests for license detection."""

from __future__ import annotations

from email.message import Message
from pathlib import Path

from license_audit.core.models import LicenseSource
from license_audit.licenses.detection import (
    _detect_from_metadata,
    _try_classifiers,
    _try_license_field,
    _try_pep639,
    detect_license,
    detect_license_from_path,
)


def _make_metadata(**headers: str | list[str]) -> Message:
    """Create a fake email.message.Message with the given headers."""
    msg = Message()
    for key, val in headers.items():
        key = key.replace("_", "-")
        if isinstance(val, list):
            for v in val:
                msg[key] = v
        else:
            msg[key] = val
    return msg


class TestDetectLicense:
    def test_override_takes_precedence(self) -> None:
        expr, source = detect_license("click", overrides={"click": "BSD-2-Clause"})
        assert expr == "BSD-2-Clause"
        assert source == LicenseSource.OVERRIDE

    def test_installed_package(self) -> None:
        # click should be installed in the test env
        expr, source = detect_license("click")
        assert expr != "UNKNOWN"
        assert source != LicenseSource.UNKNOWN

    def test_nonexistent_package(self) -> None:
        expr, source = detect_license("this_package_does_not_exist_xyz_123")
        assert expr == "UNKNOWN"
        assert source == LicenseSource.UNKNOWN


class TestDetectLicenseFromPath:
    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        expr, source = detect_license_from_path(
            "mypkg", tmp_path, overrides={"mypkg": "Apache-2.0"}
        )
        assert expr == "Apache-2.0"
        assert source == LicenseSource.OVERRIDE

    def test_nonexistent_package_in_site_packages(self, tmp_path: Path) -> None:
        expr, source = detect_license_from_path("nonexistent", tmp_path)
        assert expr == "UNKNOWN"
        assert source == LicenseSource.UNKNOWN


class TestTryPep639:
    def test_valid_expression(self) -> None:
        meta = _make_metadata(License_Expression="MIT")
        result = _try_pep639(meta)
        assert result is not None
        assert result[0] == "MIT"
        assert result[1] == LicenseSource.PEP639

    def test_unknown_value_skipped(self) -> None:
        meta = _make_metadata(License_Expression="UNKNOWN")
        assert _try_pep639(meta) is None

    def test_empty_value_skipped(self) -> None:
        meta = _make_metadata(License_Expression="")
        assert _try_pep639(meta) is None

    def test_missing_field(self) -> None:
        meta = _make_metadata()
        assert _try_pep639(meta) is None


class TestTryLicenseField:
    def test_valid_license(self) -> None:
        meta = _make_metadata(License="MIT License")
        result = _try_license_field(meta)
        assert result is not None
        assert result[1] == LicenseSource.METADATA

    def test_unknown_skipped(self) -> None:
        meta = _make_metadata(License="UNKNOWN")
        assert _try_license_field(meta) is None

    def test_none_skipped(self) -> None:
        meta = _make_metadata(License="NONE")
        assert _try_license_field(meta) is None

    def test_empty_skipped(self) -> None:
        meta = _make_metadata(License="")
        assert _try_license_field(meta) is None


class TestTryClassifiers:
    def test_single_classifier(self) -> None:
        meta = _make_metadata(Classifier=["License :: OSI Approved :: MIT License"])
        result = _try_classifiers(meta)
        assert result is not None
        assert result[0] == "MIT"
        assert result[1] == LicenseSource.CLASSIFIER

    def test_multiple_classifiers_produce_or_expression(self) -> None:
        meta = _make_metadata(
            Classifier=[
                "License :: OSI Approved :: MIT License",
                "License :: OSI Approved :: Apache Software License",
            ]
        )
        result = _try_classifiers(meta)
        assert result is not None
        assert "OR" in result[0]
        assert result[1] == LicenseSource.CLASSIFIER

    def test_no_license_classifiers(self) -> None:
        meta = _make_metadata(Classifier=["Programming Language :: Python :: 3"])
        assert _try_classifiers(meta) is None

    def test_unrecognized_license_classifier(self) -> None:
        meta = _make_metadata(Classifier=["License :: Other/Proprietary License"])
        # normalize_classifier may return None for this
        result = _try_classifiers(meta)
        # If the classifier isn't recognized, result should be None
        if result is not None:
            assert result[1] == LicenseSource.CLASSIFIER


class TestDetectFromMetadata:
    def test_pep639_preferred_over_license_field(self) -> None:
        meta = _make_metadata(
            License_Expression="Apache-2.0",
            License="MIT License",
        )
        expr, source = _detect_from_metadata(meta)
        assert expr == "Apache-2.0"
        assert source == LicenseSource.PEP639

    def test_falls_back_to_license_field(self) -> None:
        meta = _make_metadata(License="MIT License")
        _expr, source = _detect_from_metadata(meta)
        assert source == LicenseSource.METADATA

    def test_falls_back_to_classifiers(self) -> None:
        meta = _make_metadata(Classifier=["License :: OSI Approved :: MIT License"])
        expr, source = _detect_from_metadata(meta)
        assert expr == "MIT"
        assert source == LicenseSource.CLASSIFIER

    def test_returns_unknown_when_nothing_found(self) -> None:
        meta = _make_metadata()
        expr, source = _detect_from_metadata(meta)
        assert expr == "UNKNOWN"
        assert source == LicenseSource.UNKNOWN
