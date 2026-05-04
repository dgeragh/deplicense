"""Load the [tool.license-audit] section from pyproject.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from license_audit.core.models import PolicyLevel


class GroupSpec:
    """Valid dependency-group selectors.

    A selector is either a literal ('main', 'dev') or a prefixed name like
    'optional:docs' or 'group:test'.
    """

    PREFIXES: tuple[str, ...] = ("optional:", "group:")
    LITERALS: tuple[str, ...] = ("main", "dev")

    @classmethod
    def validate(cls, entry: str) -> None:
        """Raise ValueError if `entry` isn't a valid selector."""
        if entry in cls.LITERALS:
            return
        for prefix in cls.PREFIXES:
            if entry.startswith(prefix):
                if not entry[len(prefix) :]:
                    msg = (
                        f"Invalid dependency group: '{entry}' "
                        f"(missing name after prefix)"
                    )
                    raise ValueError(msg)
                return
        msg = (
            f"Invalid dependency group: '{entry}'. "
            f"Must be 'main', 'dev', 'optional:<name>', or 'group:<name>'."
        )
        raise ValueError(msg)

    @classmethod
    def validate_list(cls, entries: list[str]) -> list[str]:
        """Validate every entry and return the list unchanged."""
        for entry in entries:
            cls.validate(entry)
        return entries


class LicenseAuditConfig(BaseModel):
    """Parsed [tool.license-audit] section."""

    fail_on_unknown: bool = True
    policy: PolicyLevel = PolicyLevel.PERMISSIVE
    allowed_licenses: list[str] = Field(default_factory=list)
    denied_licenses: list[str] = Field(default_factory=list)
    overrides: dict[str, str] = Field(default_factory=dict)
    dependency_groups: list[str] | None = None
    ignored_packages: dict[str, str] = Field(default_factory=dict)
    target: str | None = None

    @field_validator("dependency_groups", mode="before")
    @classmethod
    def _validate_dependency_groups(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            msg = "dependency_groups must be a list of strings"
            raise TypeError(msg)
        return GroupSpec.validate_list(value)

    @field_validator("ignored_packages", mode="before")
    @classmethod
    def _validate_ignored_packages(
        cls,
        value: object,
    ) -> dict[str, str]:
        if not value:
            return {}
        if not isinstance(value, dict):
            # Pydantic v2 wraps ValueError into ValidationError but passes
            # TypeError through as-is, so we raise ValueError for consistent
            # error surfacing even though TypeError would be more idiomatic.
            msg = "ignored-packages must be a table mapping package name to reason"
            raise ValueError(msg)  # noqa: TRY004
        for key, reason in value.items():
            if not isinstance(reason, str) or not reason.strip():
                msg = (
                    f"ignored-packages['{key}'] must be a non-empty string "
                    f"explaining why the package is ignored"
                )
                raise ValueError(msg)
        return value


def load_config(config_dir: Path | None = None) -> LicenseAuditConfig:
    """Load config from pyproject.toml, or return defaults if none found."""
    if config_dir is None:
        config_dir = Path.cwd()

    pyproject_path = config_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return LicenseAuditConfig()

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    tool_config = data.get("tool", {}).get("license-audit", {})
    if not tool_config:
        return LicenseAuditConfig()

    # pyproject convention is kebab-case; Pydantic fields are snake_case.
    normalized: dict[str, object] = {}
    for key, value in tool_config.items():
        normalized[key.replace("-", "_")] = value

    return LicenseAuditConfig.model_validate(normalized)


def get_project_name(config_dir: Path | None = None) -> str:
    """Read [project].name from pyproject.toml, or 'unknown' if missing."""
    if config_dir is None:
        config_dir = Path.cwd()

    pyproject_path = config_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return "unknown"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    return str(data.get("project", {}).get("name", "unknown"))
