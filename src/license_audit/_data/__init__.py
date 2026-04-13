"""Bundled OSADL data with user-cache overlay."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def _cache_path(filename: str) -> Path | None:
    """Return the cached data file path if it exists."""
    # Deferred import to avoid circular dependency with cli.refresh
    import platformdirs

    cache_file = Path(platformdirs.user_cache_dir("license_audit")) / "osadl" / filename
    if cache_file.is_file():
        return cache_file
    return None


def load_data_file(filename: str) -> str:
    """Load an OSADL data file, preferring the user cache over bundled data."""
    cached = _cache_path(filename)
    if cached is not None:
        return cached.read_text(encoding="utf-8")
    data_path = resources.files("license_audit._data").joinpath(filename)
    return data_path.read_text(encoding="utf-8")
