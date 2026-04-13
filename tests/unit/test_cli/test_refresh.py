"""Tests for the refresh CLI command."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from license_audit.cli.main import cli
from license_audit.cli.refresh import _download, get_cache_dir


class TestRefreshCmd:
    def test_downloads_both_files(self, tmp_path):
        with (
            patch("license_audit.cli.refresh.get_cache_dir", return_value=tmp_path),
            patch("license_audit.cli.refresh._download") as mock_dl,
        ):
            result = CliRunner().invoke(cli, ["refresh"])

        assert result.exit_code == 0
        assert mock_dl.call_count == 2
        assert "matrix.json updated" in result.output
        assert "copyleft.json updated" in result.output
        assert "refreshed successfully" in result.output

    def test_creates_cache_directory(self, tmp_path):
        cache_dir = tmp_path / "sub" / "osadl"
        with (
            patch("license_audit.cli.refresh.get_cache_dir", return_value=cache_dir),
            patch("license_audit.cli.refresh._download"),
        ):
            result = CliRunner().invoke(cli, ["refresh"])

        assert result.exit_code == 0
        assert cache_dir.is_dir()


class TestDownload:
    def test_writes_valid_json(self, tmp_path):
        data = json.dumps({"key": "value"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        dest = tmp_path / "test.json"
        with patch("license_audit.cli.refresh.urlopen", return_value=mock_resp):
            _download("https://example.com/test.json", dest)

        assert dest.exists()
        assert json.loads(dest.read_text()) == {"key": "value"}

    def test_rejects_oversized_response(self, tmp_path):
        import pytest

        large_data = b"x" * (10 * 1024 * 1024 + 2)
        mock_resp = MagicMock()
        mock_resp.read.return_value = large_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        dest = tmp_path / "test.json"
        with (
            patch("license_audit.cli.refresh.urlopen", return_value=mock_resp),
            pytest.raises(RuntimeError, match="exceeds"),
        ):
            _download("https://example.com/test.json", dest)

        assert not dest.exists()

    def test_rejects_invalid_json(self, tmp_path):
        import pytest

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json at all"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        dest = tmp_path / "test.json"
        with (
            patch("license_audit.cli.refresh.urlopen", return_value=mock_resp),
            pytest.raises(json.JSONDecodeError),
        ):
            _download("https://example.com/test.json", dest)

    def test_network_error(self, tmp_path):
        from urllib.error import URLError

        import pytest

        dest = tmp_path / "test.json"
        with (
            patch(
                "license_audit.cli.refresh.urlopen",
                side_effect=URLError("connection refused"),
            ),
            pytest.raises(URLError),
        ):
            _download("https://example.com/test.json", dest)


class TestGetCacheDir:
    def test_returns_path(self):
        result = get_cache_dir()
        assert "license_audit" in str(result)
        assert "osadl" in str(result)
