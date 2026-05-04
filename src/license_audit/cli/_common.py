"""Shared CLI helpers."""

from __future__ import annotations

from pathlib import Path

import click

from license_audit.config import LicenseAuditConfig, load_config
from license_audit.core.analyzer import LicenseAuditor
from license_audit.core.models import AnalysisReport, PolicyLevel


def resolve_config(ctx: click.Context) -> tuple[Path | None, LicenseAuditConfig]:
    """Extract the target path and merged config from the CLI context.

    CLI flags (--target, --policy, --dependency-groups) override values
    read from pyproject.toml.
    """
    target: Path | None = ctx.obj.get("target")
    policy: str | None = ctx.obj.get("policy")
    dependency_groups: tuple[str, ...] = ctx.obj.get("dependency_groups", ())
    config_dir = target.parent if target and target.is_file() else target
    config = load_config(config_dir)
    if policy is not None:
        config.policy = PolicyLevel(policy)
    if dependency_groups:
        config.dependency_groups = list(dependency_groups)
    if target is None and config.target is not None:
        # Resolve relative paths against the pyproject dir so config is
        # portable across CI/dev machines regardless of CWD.
        base = config_dir if config_dir is not None else Path.cwd()
        target = (base / config.target).resolve()
    return target, config


def run_audit(
    target: Path | None,
    config: LicenseAuditConfig,
    auditor: LicenseAuditor | None = None,
) -> AnalysisReport:
    """Run the audit and convert user-facing errors to clean CLI messages.

    Raises `click.ClickException` on target-resolution errors so Click
    prints a concise "Error: ..." instead of a full Python traceback.
    """
    try:
        return (auditor or LicenseAuditor()).run(target=target, config=config)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
