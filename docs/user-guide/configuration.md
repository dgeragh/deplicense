# Configuration

license-audit is configured via `[tool.license-audit]` in your `pyproject.toml`.

When using `--target`, configuration is always loaded from the target project's `pyproject.toml`. For example, `--target /path/to/uv.lock` reads config from `/path/to/pyproject.toml`. If no config is found, defaults apply.

## Options

### `fail-on-unknown`

Whether to fail the `check` command when any dependency has an undetectable license. Default: `true`.

### `policy`

License policy preset. Default: `"permissive"`.

| Value | Description |
|-------|-------------|
| `"permissive"` | Only allow permissive licenses (MIT, BSD, Apache, etc.) |
| `"weak-copyleft"` | Allow permissive + weak copyleft (LGPL, MPL, etc.) |
| `"strong-copyleft"` | Allow permissive + weak + strong copyleft (GPL, etc.) |
| `"network-copyleft"` | Allow all open-source licenses including AGPL |

The policy defines the maximum copyleft level allowed. Any dependency with a license category above the policy threshold will fail the check.

This can also be set via the `--policy` CLI flag, which takes precedence over the config file:

```bash
license-audit --policy weak-copyleft check
```

### `allowed-licenses`

Explicit list of allowed SPDX identifiers. When set, only these licenses pass the policy check.

### `denied-licenses`

List of SPDX identifiers that always fail the policy check, regardless of other settings.

### `dependency-groups`

Restrict analysis to specific dependency groups. When unset, all groups are included.

Each entry is a group selector:

| Selector | Maps to |
|---|---|
| `main` | `[project.dependencies]` |
| `optional:<name>` | `[project.optional-dependencies.<name>]` |
| `group:<name>` | `[dependency-groups.<name>]` (PEP 735) |
| `dev` | `[tool.uv.dev-dependencies]` |

```toml
[tool.license-audit]
dependency-groups = ["main", "optional:api"]
```

This can also be set via the `--dependency-groups` CLI flag (repeatable), which takes precedence over the config file:

```bash
license-audit --dependency-groups main --dependency-groups optional:api check
```

For `requirements.txt` targets, this option is ignored (flat format with no group concept).

### `overrides`

Manual license assignments for packages where auto-detection fails.

```toml
[tool.license-audit.overrides]
my-internal-package = "MIT"
dual-licensed-pkg = "Apache-2.0 OR MIT"
```

## Target resolution

The `--target` CLI flag controls what license-audit analyzes. The source type is inferred automatically:

| Target | Behavior |
|--------|----------|
| *(none)* | Analyze the current Python environment directly |
| Project directory | Auto-detect: tries `uv.lock` -> `requirements.txt` -> `pyproject.toml` -> `.venv` |
| `uv.lock` | Parse lockfile, create temp environment, analyze |
| `requirements.txt` | Parse requirements, create temp environment, analyze |
| `pyproject.toml` | Parse `[project.dependencies]`, optional-dependencies, dependency-groups, and `[tool.uv.dev-dependencies]`, create temp environment, analyze |
| `.venv` directory | Analyze the venv directly (no temp environment needed) |

Examples:

```bash
license-audit analyze                                # current environment (default)
license-audit --target . analyze                     # auto-detect from current dir
license-audit --target /path/to/project analyze      # auto-detect from project dir
license-audit --target /path/to/uv.lock analyze      # parse a specific lockfile
license-audit --target /path/to/.venv analyze        # analyze an existing venv
```
