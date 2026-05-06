"""Tests for MetadataReader.from_wheel_dir."""

from __future__ import annotations

import zipfile
from pathlib import Path

from license_audit.util import MetadataReader


def _build_wheel(
    wheel_dir: Path,
    *,
    name: str,
    version: str,
    python: str = "py3",
    abi: str = "none",
    platform: str = "any",
    metadata_extra: str = "",
    license_files: dict[str, str] | None = None,
    license_subdir_files: dict[str, str] | None = None,
    extra_entries: dict[str, str] | None = None,
) -> Path:
    """Write a minimal PEP 427 wheel into `wheel_dir`."""
    filename = f"{name}-{version}-{python}-{abi}-{platform}.whl"
    wheel_path = wheel_dir / filename
    dist_info = f"{name}-{version}.dist-info"
    metadata = (
        f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n{metadata_extra}"
    )

    with zipfile.ZipFile(wheel_path, "w") as zf:
        zf.writestr(f"{dist_info}/METADATA", metadata)
        zf.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\n")
        if license_files:
            for fname, content in license_files.items():
                zf.writestr(f"{dist_info}/{fname}", content)
        if license_subdir_files:
            for fname, content in license_subdir_files.items():
                zf.writestr(f"{dist_info}/licenses/{fname}", content)
        if extra_entries:
            for entry_name, content in extra_entries.items():
                zf.writestr(entry_name, content)

    return wheel_path


class TestWheelReadMetadata:
    def test_reads_metadata_from_wheel(self, tmp_path: Path) -> None:
        _build_wheel(
            tmp_path,
            name="mypkg",
            version="1.2.3",
            metadata_extra="License-Expression: MIT\n",
        )
        reader = MetadataReader.from_wheel_dir(tmp_path)
        meta = reader.read_metadata("mypkg")
        assert meta is not None
        assert meta.get("Name") == "mypkg"
        assert meta.get("Version") == "1.2.3"
        assert meta.get("License-Expression") == "MIT"

    def test_missing_package_returns_none(self, tmp_path: Path) -> None:
        _build_wheel(tmp_path, name="other", version="1.0")
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert reader.read_metadata("absent") is None

    def test_canonicalizes_name(self, tmp_path: Path) -> None:
        _build_wheel(tmp_path, name="my_cool_pkg", version="1.0")
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert reader.read_metadata("my-cool-pkg") is not None
        assert reader.read_metadata("My.Cool.Pkg") is not None

    def test_empty_wheel_dir(self, tmp_path: Path) -> None:
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert reader.read_metadata("anything") is None

    def test_iter_package_names(self, tmp_path: Path) -> None:
        _build_wheel(tmp_path, name="alpha", version="1.0")
        _build_wheel(tmp_path, name="beta", version="2.0")
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert sorted(reader.iter_package_names()) == ["alpha", "beta"]

    def test_describe_source(self, tmp_path: Path) -> None:
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert reader.describe_source() == str(tmp_path)


class TestWheelLicenseText:
    def test_pep639_license_under_licenses_dir(self, tmp_path: Path) -> None:
        _build_wheel(
            tmp_path,
            name="pep639_pkg",
            version="1.0",
            metadata_extra="License-File: LICENSE\n",
            license_subdir_files={"LICENSE": "Apache 2.0 text"},
        )
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert reader.read_license_text("pep639_pkg") == "Apache 2.0 text"

    def test_pep639_license_at_dist_info_root(self, tmp_path: Path) -> None:
        _build_wheel(
            tmp_path,
            name="legacy_lic",
            version="1.0",
            metadata_extra="License-File: LICENSE\n",
            license_files={"LICENSE": "MIT text"},
        )
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert reader.read_license_text("legacy_lic") == "MIT text"

    def test_multiple_license_files(self, tmp_path: Path) -> None:
        _build_wheel(
            tmp_path,
            name="multi",
            version="1.0",
            metadata_extra="License-File: LICENSE\nLicense-File: NOTICE\n",
            license_subdir_files={
                "LICENSE": "License body",
                "NOTICE": "Notice body",
            },
        )
        result = MetadataReader.from_wheel_dir(tmp_path).read_license_text("multi")
        assert result is not None
        assert "License body" in result
        assert "Notice body" in result

    def test_fallback_common_pattern(self, tmp_path: Path) -> None:
        _build_wheel(
            tmp_path,
            name="fallback",
            version="1.0",
            license_files={"COPYING.txt": "GPL text"},
        )
        result = MetadataReader.from_wheel_dir(tmp_path).read_license_text("fallback")
        assert result is not None
        assert "GPL text" in result

    def test_no_license_returns_none(self, tmp_path: Path) -> None:
        _build_wheel(tmp_path, name="bare", version="1.0")
        assert MetadataReader.from_wheel_dir(tmp_path).read_license_text("bare") is None


class TestWheelEdgeCases:
    def test_malformed_wheel_no_dist_info(self, tmp_path: Path) -> None:
        wheel = tmp_path / "broken-1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as zf:
            zf.writestr("broken/__init__.py", "")
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert reader.read_metadata("broken") is None

    def test_wheel_with_dist_info_but_no_metadata(self, tmp_path: Path) -> None:
        wheel = tmp_path / "nometa-1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as zf:
            zf.writestr("nometa-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\n")
            zf.writestr("nometa-1.0.dist-info/RECORD", "")
        reader = MetadataReader.from_wheel_dir(tmp_path)
        assert reader.read_metadata("nometa") is None

    def test_duplicate_wheels_pick_lexicographic_last(self, tmp_path: Path) -> None:
        _build_wheel(
            tmp_path,
            name="dup",
            version="1.0",
            metadata_extra="License-Expression: MIT\n",
        )
        _build_wheel(
            tmp_path,
            name="dup",
            version="1.1",
            metadata_extra="License-Expression: Apache-2.0\n",
        )
        reader = MetadataReader.from_wheel_dir(tmp_path)
        meta = reader.read_metadata("dup")
        assert meta is not None
        assert meta.get("Version") == "1.1"
        assert meta.get("License-Expression") == "Apache-2.0"

    def test_dist_info_lookup_caches(self, tmp_path: Path) -> None:
        _build_wheel(tmp_path, name="cached", version="1.0")
        reader = MetadataReader.from_wheel_dir(tmp_path)
        first = reader.read_metadata("cached")
        # Delete the wheel; the cached read should still serve.
        next(tmp_path.glob("*.whl")).unlink()
        second = reader.read_metadata("cached")
        assert first is not None
        assert second is not None
        assert first.get("Name") == second.get("Name")

    def test_iter_package_names_deduplicates(self, tmp_path: Path) -> None:
        _build_wheel(tmp_path, name="dup", version="1.0")
        _build_wheel(tmp_path, name="dup", version="1.1")
        names = list(MetadataReader.from_wheel_dir(tmp_path).iter_package_names())
        assert names == ["dup"]
