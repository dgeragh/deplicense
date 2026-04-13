# CI Integration

## GitHub Actions

Add to your CI workflow:

```yaml
- name: License check
  run: uv run license-audit check
```

### Full Example

```yaml
name: CI
on: [push, pull_request]

jobs:
  license-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --locked
      - run: uv run license-audit check
```

## Policy Override

Use the `--policy` flag to set the license policy level without changing `pyproject.toml`. This is useful for running different policy checks in separate CI jobs:

```yaml
- name: Strict permissive check
  run: uv run license-audit --policy permissive check

- name: Allow weak copyleft
  run: uv run license-audit --policy weak-copyleft check
```

Available policy levels: `permissive`, `weak-copyleft`, `strong-copyleft`, `network-copyleft`.

## Check Options

The `check` command supports the `--fail-on-unknown/--no-fail-on-unknown` flag to control whether undetected licenses cause a failure, overriding the `fail-on-unknown` config option:

```bash
uv run license-audit check --fail-on-unknown       # fail on unknown licenses (default)
uv run license-audit check --no-fail-on-unknown     # allow unknown licenses
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All dependencies pass the license policy |
| `1` | Policy violation (incompatible or denied licenses) |
| `2` | Unknown licenses detected (when `fail-on-unknown = true`) |

## Generating Reports in CI

```yaml
- name: Generate license report
  run: uv run license-audit report --output COMPLIANCE.md

- name: Generate third-party notices
  run: uv run license-audit report --format notices --output THIRD_PARTY_NOTICES.md

- name: Upload compliance artifacts
  uses: actions/upload-artifact@v4
  with:
    name: license-report
    path: |
      COMPLIANCE.md
      THIRD_PARTY_NOTICES.md
```
