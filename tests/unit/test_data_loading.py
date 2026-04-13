"""Tests for OSADL data loading with cache overlay."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from license_audit._data import load_data_file


class TestLoadDataFile:
    def test_loads_bundled_data_by_default(self) -> None:
        # Should load the bundled osadl_matrix.json without error
        content = load_data_file("osadl_matrix.json")
        data = json.loads(content)
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_loads_bundled_copyleft_data(self) -> None:
        content = load_data_file("copyleft.json")
        data = json.loads(content)
        assert "copyleft" in data

    def test_prefers_cached_file(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "osadl" / "test.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text('{"cached": true}')

        with patch(
            "platformdirs.user_cache_dir",
            return_value=str(tmp_path),
        ):
            content = load_data_file("test.json")

        assert json.loads(content) == {"cached": True}

    def test_falls_back_to_bundled_when_no_cache(self, tmp_path: Path) -> None:
        with patch(
            "platformdirs.user_cache_dir",
            return_value=str(tmp_path),
        ):
            # No cache file exists, should fall back to bundled
            content = load_data_file("osadl_matrix.json")

        data = json.loads(content)
        assert isinstance(data, dict)
        assert len(data) > 0
