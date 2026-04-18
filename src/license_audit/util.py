"""Shared utilities for package name handling and metadata reading."""

from __future__ import annotations

from email.parser import HeaderParser
from pathlib import Path
from typing import Any


def canonicalize(name: str) -> str:
    """Canonicalize a package name per PEP 503.

    Lowercases and maps hyphens and dots to underscores so names compare
    equal regardless of how they were written on PyPI.
    """
    return name.lower().replace("-", "_").replace(".", "_")


class MetadataReader:
    """Reads METADATA and license files out of a site-packages directory."""

    LICENSE_FILE_PATTERNS: tuple[str, ...] = (
        "LICENSE*",
        "LICENCE*",
        "COPYING*",
        "NOTICE*",
    )

    def __init__(self) -> None:
        self._parser = HeaderParser()

    def read_metadata(self, package_name: str, site_packages: Path) -> Any | None:
        """Parse METADATA for `package_name` under `site_packages`.

        Returns the parsed email-style headers, or None if no matching
        `*.dist-info/METADATA` file exists.
        """
        dist_info = self._find_dist_info(package_name, site_packages)
        if dist_info is None:
            return None
        metadata_file = dist_info / "METADATA"
        if not metadata_file.exists():
            return None
        return self._parser.parsestr(metadata_file.read_text(encoding="utf-8"))

    def read_license_text(
        self,
        package_name: str,
        site_packages: Path,
    ) -> str | None:
        """Concatenated license-file text for `package_name`.

        Prefers files declared in PEP 639 `License-File` metadata, falling
        back to common filename patterns like LICENSE, COPYING, NOTICE.
        Returns None if no license files are found.
        """
        dist_info = self._find_dist_info(package_name, site_packages)
        if dist_info is None:
            return None

        texts = self._read_pep639_license_files(dist_info)
        if not texts:
            texts = self._read_common_license_files(dist_info)
        return "\n".join(texts) if texts else None

    def _find_dist_info(
        self,
        package_name: str,
        site_packages: Path,
    ) -> Path | None:
        canonical = canonicalize(package_name)
        for dist_info in site_packages.glob("*.dist-info"):
            dir_name = dist_info.name.rsplit(".dist-info", 1)[0]
            dist_name = canonicalize(dir_name.split("-", 1)[0])
            if dist_name == canonical:
                return dist_info
        return None

    def _read_pep639_license_files(self, dist_info: Path) -> list[str]:
        metadata_file = dist_info / "METADATA"
        if not metadata_file.exists():
            return []
        meta = self._parser.parsestr(metadata_file.read_text(encoding="utf-8"))
        texts: list[str] = []
        for lf in meta.get_all("License-File") or []:
            # PEP 639 keeps the file under licenses/ but stores only the
            # bare filename in metadata, so check both locations.
            for candidate in (dist_info / lf, dist_info / "licenses" / lf):
                if candidate.is_file():
                    texts.append(
                        candidate.read_text(encoding="utf-8", errors="replace")
                    )
                    break
        return texts

    def _read_common_license_files(self, dist_info: Path) -> list[str]:
        texts: list[str] = []
        search_dirs = [dist_info]
        licenses_dir = dist_info / "licenses"
        if licenses_dir.is_dir():
            search_dirs.append(licenses_dir)
        for directory in search_dirs:
            for pattern in self.LICENSE_FILE_PATTERNS:
                for path in directory.glob(pattern):
                    if path.is_file():
                        texts.append(path.read_text(encoding="utf-8", errors="replace"))
        return texts
