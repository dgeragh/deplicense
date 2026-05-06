"""Top-level license audit pipeline."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

from license_audit.config import LicenseAuditConfig, get_project_name, load_config
from license_audit.core.classifier import LicenseClassifier
from license_audit.core.compatibility import CompatibilityMatrix
from license_audit.core.models import (
    UNKNOWN_LICENSE,
    AnalysisReport,
    DependencyNode,
    LicenseCategory,
    PackageLicense,
)
from license_audit.core.policy import PolicyEngine
from license_audit.core.recommender import LicenseRecommender
from license_audit.environment.analyze import (
    analyze_environment,
    analyze_installed_packages,
)
from license_audit.environment.provision import EnvironmentProvisioner, ProvisionedEnv
from license_audit.licenses.expression import ExpressionEvaluator
from license_audit.licenses.spdx import SpdxNormalizer
from license_audit.sources.base import PackageSpec, Source
from license_audit.sources.factory import SourceFactory
from license_audit.util import canonicalize


@dataclass
class TargetInfo:
    """Resolved --target: which source file and/or venv to audit."""

    source_path: Path | None = None
    site_packages: Path | None = None
    config_dir: Path | None = None


class TargetResolver:
    """Classifies a --target path as source file, venv, or project dir."""

    def __init__(
        self,
        source_factory: SourceFactory | None = None,
        provisioner: EnvironmentProvisioner | None = None,
    ) -> None:
        self._sources = source_factory or SourceFactory()
        self._provisioner = provisioner or EnvironmentProvisioner()

    def resolve(self, target: Path | None) -> TargetInfo:
        """Resolve `target` into a TargetInfo.

        Raises FileNotFoundError if `target` points nowhere, or ValueError
        if it's a file we don't know how to parse.
        """
        if target is None:
            return TargetInfo(config_dir=Path.cwd())

        resolved = target.resolve()

        if resolved.is_file():
            self._sources.validate(resolved)
            return TargetInfo(source_path=resolved, config_dir=resolved.parent)

        if self._provisioner.is_venv_dir(resolved):
            return TargetInfo(site_packages=resolved, config_dir=resolved.parent)

        if resolved.is_dir():
            return self._detect_in_project_dir(resolved)

        msg = f"Target not found: {resolved}"
        raise FileNotFoundError(msg)

    def _detect_in_project_dir(self, project_dir: Path) -> TargetInfo:
        found = self._sources.detect_in_project_dir(project_dir)
        if found is not None:
            return TargetInfo(source_path=found, config_dir=project_dir)

        venv = project_dir / ".venv"
        if venv.is_dir():
            return TargetInfo(site_packages=venv, config_dir=project_dir)

        msg = (
            f"No dependency source found in {project_dir}. "
            "Expected uv.lock, requirements.txt, pyproject.toml, or .venv"
        )
        raise FileNotFoundError(msg)


class LicenseAuditor:
    """Runs the full audit pipeline and returns an AnalysisReport.

    Each collaborator is injectable so tests can swap pieces, but a plain
    `LicenseAuditor().run(target=Path('.'))` works without any setup.
    """

    def __init__(
        self,
        resolver: TargetResolver | None = None,
        source_factory: SourceFactory | None = None,
        provisioner: EnvironmentProvisioner | None = None,
        classifier: LicenseClassifier | None = None,
        matrix: CompatibilityMatrix | None = None,
        normalizer: SpdxNormalizer | None = None,
        recommender: LicenseRecommender | None = None,
        policy: PolicyEngine | None = None,
        expression: ExpressionEvaluator | None = None,
    ) -> None:
        self._matrix = matrix or CompatibilityMatrix()
        self._classifier = classifier or LicenseClassifier()
        self._normalizer = normalizer or SpdxNormalizer(matrix=self._matrix)
        self._expression = expression or ExpressionEvaluator(
            classifier=self._classifier,
            normalizer=self._normalizer,
        )
        self._recommender = recommender or LicenseRecommender(
            matrix=self._matrix,
            classifier=self._classifier,
            normalizer=self._normalizer,
        )
        self._policy = policy or PolicyEngine(
            classifier=self._classifier,
            normalizer=self._normalizer,
            expression=self._expression,
        )
        self._sources = source_factory or SourceFactory()
        self._provisioner = provisioner or EnvironmentProvisioner()
        self._resolver = resolver or TargetResolver(
            source_factory=self._sources,
            provisioner=self._provisioner,
        )

    def run(
        self,
        target: Path | None = None,
        config: LicenseAuditConfig | None = None,
    ) -> AnalysisReport:
        """Run the audit pipeline against `target` and return the report."""
        info = self._resolver.resolve(target)

        if config is None:
            config = load_config(info.config_dir)

        project_name = get_project_name(info.config_dir)
        self._warn_if_groups_ignored(info, config)

        source = self._build_source(info, config)
        specs, env = self._provision(info, source)

        with env:
            tree = self._build_tree(
                project_name,
                env,
                specs,
                dict(config.overrides),
            )
            packages = tree.flatten()
            self._classify_packages(packages)
            self._collect_license_text(packages, env)
            self._apply_ignores(packages, config.ignored_packages)

            dep_packages = [p for p in packages if p.name != canonicalize(project_name)]
            active_packages = [p for p in dep_packages if not p.ignored]
            dep_licenses = [p.license_expression for p in active_packages]
            dep_spdx_ids = self._extract_spdx_ids(dep_licenses)

            has_unknown = any(
                p.category == LicenseCategory.UNKNOWN for p in active_packages
            )
            recommended = (
                [] if has_unknown else self._recommender.recommend(dep_licenses)
            )
            incompatible = self._matrix.find_incompatible_pairs(dep_spdx_ids)
            action_items = self._policy.build_action_items(
                dep_packages,
                incompatible,
                config,
            )
            policy_passed = self._policy.check(
                dep_packages,
                self._policy.build_policy(config),
            )

        return AnalysisReport(
            project_name=project_name,
            source=self._describe_source(info),
            packages=dep_packages,
            incompatible_pairs=incompatible,
            recommended_licenses=recommended,
            action_items=action_items,
            policy_passed=policy_passed,
        )

    @staticmethod
    def _describe_source(info: TargetInfo) -> str:
        if info.source_path is not None:
            return str(info.source_path)
        if info.site_packages is not None:
            return str(info.site_packages)
        return "active environment"

    def _warn_if_groups_ignored(
        self,
        info: TargetInfo,
        config: LicenseAuditConfig,
    ) -> None:
        if (
            config.dependency_groups
            and info.source_path is None
            and info.site_packages is None
        ):
            warnings.warn(
                "dependency-groups is configured but no target was resolved. "
                'Pass --target . on the CLI, or add `target = "."` to '
                "[tool.license-audit] in your pyproject.toml.",
                UserWarning,
                stacklevel=3,
            )

    def _build_source(
        self,
        info: TargetInfo,
        config: LicenseAuditConfig,
    ) -> Source | None:
        if info.source_path is None:
            return None
        return self._sources.create(info.source_path, config.dependency_groups)

    def _provision(
        self,
        info: TargetInfo,
        source: Source | None,
    ) -> tuple[list[PackageSpec] | None, ProvisionedEnv]:
        if info.site_packages is not None:
            return None, self._provisioner.from_venv(info.site_packages)
        if source is not None:
            specs = source.parse()
            return specs, self._provisioner.temp(specs)
        return None, self._provisioner.current()

    def _build_tree(
        self,
        project_name: str,
        env: ProvisionedEnv,
        specs: list[PackageSpec] | None,
        overrides: dict[str, str],
    ) -> DependencyNode:
        if specs is not None:
            pkg_extras = {s.name: s.extras for s in specs if s.extras}
            return analyze_installed_packages(
                project_name,
                env.reader,
                [s.name for s in specs],
                overrides,
                pkg_extras,
            )
        return analyze_environment(project_name, env.reader, overrides)

    def _classify_packages(self, packages: list[PackageLicense]) -> None:
        for pkg in packages:
            if pkg.license_expression != UNKNOWN_LICENSE:
                self._classify_package(pkg)

    def _classify_package(self, pkg: PackageLicense) -> None:
        pkg.category = self._expression.classify(pkg.license_expression)

    def _collect_license_text(
        self,
        packages: list[PackageLicense],
        env: ProvisionedEnv,
    ) -> None:
        for pkg in packages:
            pkg.license_text = env.reader.read_license_text(pkg.name)

    def _apply_ignores(
        self,
        packages: list[PackageLicense],
        ignored_packages: dict[str, str],
    ) -> None:
        """Mark packages listed in config.ignored_packages as ignored."""
        if not ignored_packages:
            return
        reasons = {
            canonicalize(name): reason for name, reason in ignored_packages.items()
        }
        for pkg in packages:
            reason = reasons.get(pkg.name)
            if reason is not None:
                pkg.ignored = True
                pkg.ignore_reason = reason

    def _extract_spdx_ids(self, expressions: list[str]) -> list[str]:
        ids: set[str] = set()
        for expr in expressions:
            if expr != UNKNOWN_LICENSE:
                for lic in self._expression.required_ids(expr):
                    ids.add(lic)
        return list(ids)
