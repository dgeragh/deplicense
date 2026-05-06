"""Tests for EnvironmentProvisioner.temp() and helpers."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from license_audit.environment.provision import (
    EnvironmentProvisioner,
    ProvisionedEnv,
)
from license_audit.sources.base import PackageSpec
from license_audit.util import MetadataReader


def _ok(returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["pip"], returncode=returncode, stdout="", stderr=""
    )


def _write_fake_wheel(
    wheel_dir: Path,
    name: str,
    version: str,
    metadata_extra: str = "",
) -> Path:
    """Write a minimal wheel into `wheel_dir`."""
    wheel_dir.mkdir(exist_ok=True)
    wheel = wheel_dir / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr(
            f"{name}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n{metadata_extra}",
        )
    return wheel


class TestSpecToInstallArg:
    def test_registry_package(self) -> None:
        spec = PackageSpec(name="click", version_constraint=">=8.0")
        assert EnvironmentProvisioner._spec_to_install_arg(spec) == "click>=8.0"

    def test_url_package(self) -> None:
        spec = PackageSpec(
            name="mypkg",
            version_constraint="",
            source_url="git+https://github.com/user/mypkg.git",
        )
        assert (
            EnvironmentProvisioner._spec_to_install_arg(spec)
            == "mypkg @ git+https://github.com/user/mypkg.git"
        )

    def test_no_version_constraint(self) -> None:
        spec = PackageSpec(name="click", version_constraint="")
        assert EnvironmentProvisioner._spec_to_install_arg(spec) == "click"


class TestTempEmptySpecs:
    def test_no_pip_invocation_for_empty_specs(self, tmp_path: Path) -> None:
        provisioner = EnvironmentProvisioner()
        with patch.object(EnvironmentProvisioner, "_run_pip") as mock_run:
            env = provisioner.temp([])
            with env:
                assert mock_run.call_count == 0
                assert isinstance(env.reader, MetadataReader)


class TestTempCommandLine:
    def test_pip_wheel_command_line(self, tmp_path: Path) -> None:
        provisioner = EnvironmentProvisioner()
        captured: list[list[str]] = []

        def fake_run(
            base_cmd: list[str], extra_args: list[str]
        ) -> subprocess.CompletedProcess[str]:
            captured.append([*base_cmd, *extra_args])
            wheel_dir = Path(base_cmd[base_cmd.index("-w") + 1])
            _write_fake_wheel(wheel_dir, "click", "8.1.0")
            return _ok()

        spec = PackageSpec(name="click", version_constraint=">=8.0")
        with patch.object(EnvironmentProvisioner, "_run_pip", side_effect=fake_run):
            env = provisioner.temp([spec])
            with env:
                assert env.reader.read_metadata("click") is not None

        assert len(captured) == 1
        cmd = captured[0]
        assert cmd[0] == sys.executable
        assert cmd[1:5] == ["-m", "pip", "wheel", "--pre"]
        assert "-w" in cmd
        assert "click>=8.0" in cmd

    def test_url_spec_passed_through(self, tmp_path: Path) -> None:
        provisioner = EnvironmentProvisioner()
        captured: list[list[str]] = []

        def fake_run(
            base_cmd: list[str], extra_args: list[str]
        ) -> subprocess.CompletedProcess[str]:
            captured.append([*base_cmd, *extra_args])
            wheel_dir = Path(base_cmd[base_cmd.index("-w") + 1])
            _write_fake_wheel(wheel_dir, "remote", "1.0")
            return _ok()

        spec = PackageSpec(
            name="remote",
            version_constraint="",
            source_url="git+https://example.com/remote.git",
        )
        with (
            patch.object(EnvironmentProvisioner, "_run_pip", side_effect=fake_run),
            provisioner.temp([spec]),
        ):
            pass

        assert "remote @ git+https://example.com/remote.git" in captured[0]


class TestTempFallbacks:
    def test_per_package_fallback_when_batch_fails(self, tmp_path: Path) -> None:
        """When batch pip wheel fails, each spec is retried alone."""
        provisioner = EnvironmentProvisioner()
        calls: list[list[str]] = []

        def fake_run(
            base_cmd: list[str], extra_args: list[str]
        ) -> subprocess.CompletedProcess[str]:
            calls.append(extra_args)
            wheel_dir = Path(base_cmd[base_cmd.index("-w") + 1])
            # Multi-spec call fails; single-spec retries succeed.
            if len(extra_args) > 1:
                return _ok(returncode=1)
            _write_fake_wheel(wheel_dir, extra_args[0].split(">=")[0], "1.0")
            return _ok()

        specs = [
            PackageSpec(name="click", version_constraint=">=8.0"),
            PackageSpec(name="rich", version_constraint=">=13.0"),
        ]
        with (
            patch.object(EnvironmentProvisioner, "_run_pip", side_effect=fake_run),
            provisioner.temp(specs),
        ):
            pass

        # 1 batch call + 2 per-package retries
        assert len(calls) == 3
        assert calls[0] == ["click>=8.0", "rich>=13.0"]
        assert calls[1] == ["click>=8.0"]
        assert calls[2] == ["rich>=13.0"]

    def test_name_only_fallback(self, tmp_path: Path) -> None:
        """When the constrained spec fails, retry with the bare name.

        Lets a yanked or unpublished version fall back to whatever's
        currently on PyPI rather than killing the run.
        """
        provisioner = EnvironmentProvisioner()
        calls: list[list[str]] = []

        def fake_run(
            base_cmd: list[str], extra_args: list[str]
        ) -> subprocess.CompletedProcess[str]:
            calls.append(extra_args)
            # Anything with a version constraint fails; bare name succeeds.
            if any(c in extra_args[0] for c in (">=", "==", "<")):
                return _ok(returncode=1)
            wheel_dir = Path(base_cmd[base_cmd.index("-w") + 1])
            _write_fake_wheel(wheel_dir, extra_args[0], "9.9.9")
            return _ok()

        spec = PackageSpec(name="click", version_constraint=">=999.0")
        with (
            patch.object(EnvironmentProvisioner, "_run_pip", side_effect=fake_run),
            provisioner.temp([spec]),
        ):
            pass

        # batch fails, per-spec fails, bare name succeeds
        assert calls == [["click>=999.0"], ["click>=999.0"], ["click"]]


class TestTempCleanup:
    def test_cleans_up_on_failure(self, tmp_path: Path) -> None:
        provisioner = EnvironmentProvisioner()
        created_tmp_dirs: list[MagicMock] = []

        original_tempdir = __import__(
            "license_audit.environment.provision",
            fromlist=["tempfile"],
        ).tempfile.TemporaryDirectory

        def fake_tempdir(*args: object, **kwargs: object) -> MagicMock:
            real = original_tempdir(*args, **kwargs)
            mock = MagicMock(wraps=real)
            # `wraps` forwards most attrs, but MagicMock.name is reserved
            # for repr — set it manually.
            mock.name = real.name
            created_tmp_dirs.append(mock)
            return mock

        with (
            patch(
                "license_audit.environment.provision.tempfile.TemporaryDirectory",
                side_effect=fake_tempdir,
            ),
            patch(
                "license_audit.environment.provision.atexit.unregister",
            ) as mock_unregister,
            patch.object(
                EnvironmentProvisioner,
                "_run_pip",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            provisioner.temp([PackageSpec(name="click", version_constraint=">=8.0")])

        assert len(created_tmp_dirs) == 1
        created_tmp_dirs[0].cleanup.assert_called()
        mock_unregister.assert_called_once_with(created_tmp_dirs[0].cleanup)

    def test_subprocess_error_wrapped_as_runtime_error(self, tmp_path: Path) -> None:
        provisioner = EnvironmentProvisioner()
        with (
            patch.object(
                EnvironmentProvisioner,
                "_run_pip",
                side_effect=subprocess.CalledProcessError(
                    1, "pip", stderr="resolve failed"
                ),
            ),
            pytest.raises(RuntimeError, match="Failed to provision"),
        ):
            provisioner.temp([PackageSpec(name="click", version_constraint=">=8.0")])


class TestProvisionedEnvCleanup:
    def _reader(self, tmp_path: Path) -> MetadataReader:
        return MetadataReader.from_site_packages(tmp_path)

    def test_cleanup_is_idempotent(self, tmp_path: Path) -> None:
        mock_tmp = MagicMock()
        env = ProvisionedEnv(reader=self._reader(tmp_path), _tmp_dir=mock_tmp)
        env.cleanup()
        env.cleanup()
        mock_tmp.cleanup.assert_called_once()

    def test_context_manager_calls_cleanup(self, tmp_path: Path) -> None:
        mock_tmp = MagicMock()
        env = ProvisionedEnv(reader=self._reader(tmp_path), _tmp_dir=mock_tmp)
        with env:
            pass
        mock_tmp.cleanup.assert_called_once()

    def test_no_tmp_dir_cleanup_safe(self, tmp_path: Path) -> None:
        env = ProvisionedEnv(reader=self._reader(tmp_path))
        env.cleanup()  # Should not raise

    def test_cleanup_unregisters_atexit(self, tmp_path: Path) -> None:
        """Explicit cleanup removes the atexit safety net to prevent accumulation."""
        mock_tmp = MagicMock()
        env = ProvisionedEnv(reader=self._reader(tmp_path), _tmp_dir=mock_tmp)
        with patch(
            "license_audit.environment.provision.atexit.unregister",
        ) as mock_unregister:
            env.cleanup()
        mock_unregister.assert_called_once_with(mock_tmp.cleanup)
