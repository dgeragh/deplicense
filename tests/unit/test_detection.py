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
)
from license_audit.util import MetadataReader


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


def _write_dist_info(
    site_packages: Path,
    name: str,
    version: str,
    metadata_extra: str = "",
) -> None:
    dist_info = site_packages / f"{name}-{version}.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n{metadata_extra}"
    )


class TestDetectLicense:
    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        reader = MetadataReader.from_site_packages(tmp_path)
        expr, source = detect_license(
            "mypkg",
            reader,
            overrides={"mypkg": "Apache-2.0"},
        )
        assert expr == "Apache-2.0"
        assert source == LicenseSource.OVERRIDE

    def test_reads_from_dist_info(self, tmp_path: Path) -> None:
        _write_dist_info(
            tmp_path,
            "tools",
            "1.0.0",
            metadata_extra="License-Expression: MIT\n",
        )
        reader = MetadataReader.from_site_packages(tmp_path)
        expr, source = detect_license("tools", reader)
        assert expr == "MIT"
        assert source == LicenseSource.PEP639

    def test_nonexistent_package(self, tmp_path: Path) -> None:
        reader = MetadataReader.from_site_packages(tmp_path)
        expr, source = detect_license("nonexistent", reader)
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
        result = _try_classifiers(meta)
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
