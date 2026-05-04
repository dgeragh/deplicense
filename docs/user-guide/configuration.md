# Configuration

license-audit is configured via `[tool.license-audit]` in your `pyproject.toml`.

When using `--target`, configuration is loaded from the target project's `pyproject.toml`. So `--target /path/to/uv.lock` reads its config from `/path/to/pyproject.toml`. If no config is found, defaults apply.

## Options

### `fail-on-unknown`

Whether the `check` command fails when a dependency has an undetectable license. Default: `true`.

### `policy`

License policy preset. Default: `"permissive"`.

| Value | Description |
|-------|-------------|
| `"permissive"` | Only allow permissive licenses (MIT, BSD, Apache, etc.) |
| `"weak-copyleft"` | Allow permissive + weak copyleft (LGPL, MPL, etc.) |
| `"strong-copyleft"` | Allow permissive + weak + strong copyleft (GPL, etc.) |
| `"network-copyleft"` | Allow all open-source licenses including AGPL |

Each preset sets the maximum copyleft level allowed; anything above the threshold fails the check.

The `--policy` CLI flag overrides this setting:

```bash
license-audit --policy weak-copyleft check
```

### `allowed-licenses`

Explicit list of allowed SPDX identifiers. When set, only these licenses pass the policy check, narrowing whatever `policy` would otherwise allow.

### `denied-licenses`

SPDX identifiers that always fail the policy check, regardless of `policy` or `allowed-licenses`.

### `dependency-groups`

Restricts analysis to specific groups. When unset, all groups are included.

Each entry is a group selector:

| Selector | Maps to |
|---|---|
| `main` | `[project.dependencies]` |
| `dev` | `[tool.uv.dev-dependencies]` |
| `optional:<name>` | `[project.optional-dependencies.<name>]` |
| `group:<name>` | `[dependency-groups.<name>]` (PEP 735) |

```toml
[tool.license-audit]
dependency-groups = ["main", "optional:api"]
```

The `--dependency-groups` CLI flag (repeatable) overrides this setting:

```bash
license-audit --dependency-groups main --dependency-groups optional:api check
```

Source-specific notes:

- `requirements.txt` ignores this option (flat format with no group concept).
- `poetry.lock` rejects `optional:<extra>` because the lock file doesn't preserve which extras own which packages. Use `pyproject.toml` if you need extras filtering.
- `pixi.lock` maps environments to selectors: `default` -> `main`, `dev` -> `dev`, anything else via `group:<env_name>`. `optional:<name>` is rejected because pixi doesn't have an extras concept.

### `target`

Default `--target` to use when none is supplied on the CLI. Relative paths resolve against the directory containing `pyproject.toml`.

```toml
[tool.license-audit]
target = "."
```

The CLI `--target` flag overrides this setting:

```bash
license-audit --target /path/to/other check
```

When `target` is unset and `--target` is omitted, license-audit falls back to analyzing the active Python environment (see "Target resolution" below).

### `overrides`

Manual license assignments for packages where auto-detection fails.

```toml
[tool.license-audit.overrides]
my-internal-package = "MIT"
dual-licensed-pkg = "Apache-2.0 OR MIT"
```

### `ignored-packages`

Exempt specific packages from policy evaluation. Each entry is a reason string that ends up in the audit trail.

```toml
[tool.license-audit.ignored-packages]
pandas-stubs = "Stubs only, not redistributed"
internal-tool = "Vendored, excluded from dist"
```

Ignored packages are skipped by `check`'s policy evaluation (no exit 1 or 2), excluded from incompatible-pair analysis (so they don't constrain recommendations), and still listed in every report (terminal, markdown, JSON, notices) with an `ignored` marker plus the reason.

The reason is required and must be non-empty; empty reasons are rejected at config load. Package names are canonicalized per PEP 503, so `pandas-stubs`, `pandas_stubs`, and `Pandas.Stubs` all match.

Use `overrides` when you want to re-assert what the license is. Use `ignored-packages` when the license is correct but doesn't apply to your situation (e.g. the package isn't shipped, or you've reviewed it manually and accepted the risk).

## Target resolution

The `--target` flag (or `target` field in `[tool.license-audit]`) controls what license-audit analyzes. The source type is inferred from the target:

| Target | Behavior |
|--------|----------|
| *(none)* | Analyze the current Python environment directly |
| Project directory | Auto-detect: tries `uv.lock` -> `poetry.lock` -> `pixi.lock` -> `requirements.txt` -> `pyproject.toml` -> `.venv` |
| `uv.lock` | Parse lockfile, create temp environment, analyze |
| `poetry.lock` | Parse lockfile (lock format 1.x and 2.x), create temp environment, analyze |
| `pixi.lock` | Parse lockfile, audit PyPI packages for the host platform; conda packages are skipped with a warning |
| `requirements.txt` | Parse requirements, create temp environment, analyze |
| `pyproject.toml` | Parse `[project.dependencies]`, optional-dependencies, dependency-groups, and `[tool.uv.dev-dependencies]`, create temp environment, analyze |
| `.venv` directory | Analyze the venv directly (no temp environment needed) |

Examples:

```bash
license-audit analyze                                # current environment (default)
license-audit --target . analyze                     # auto-detect from current dir
license-audit --target /path/to/project analyze      # auto-detect from project dir
license-audit --target /path/to/uv.lock analyze      # parse a specific lock file
license-audit --target /path/to/.venv analyze        # analyze an existing venv
```
