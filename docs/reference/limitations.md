# Limitations

## Detection is package-level

license-audit reads what's declared in package metadata: PEP 639 fields, the legacy `License` field, trove classifiers. It does not scan `LICENSE` or `NOTICE` files inside dependencies, and it can't detect bundled or vendored code whose license differs from the package's declaration. For file-level scanning, use [ScanCode](https://github.com/nexB/scancode-toolkit).

## OSADL coverage is finite

The OSADL compatibility matrix covers about 120 well-known open-source licenses. Niche, custom, or proprietary licenses produce "Unknown" verdicts. Use `[tool.license-audit.overrides]` to assign SPDX identifiers manually when detection fails.

## OSADL is conservative

The matrix encodes a strict reading of license compatibility. For weak-copyleft licenses (LGPL, MPL) it typically excludes permissive outbound combinations even though dynamic linking or unmodified redistribution often makes those acceptable in practice. Treat the matrix as a default guardrail, not a final answer.

## License strings on PyPI are messy

PyPI packages use inconsistent license strings. license-audit normalizes 60+ common aliases to SPDX identifiers, but uncommon or malformed strings will be reported as UNKNOWN. Overrides fill the gap.

## Source-format quirks

- `requirements.txt` is flat: only direct dependencies in the file are parsed. Transitive packages get pulled in when the temp environment is provisioned, but the parser itself only sees what's written down.
- `uv.lock` has no formal spec. The parser supports lock-format version 1 and fails explicitly on anything else.
- `poetry.lock` doesn't preserve the project-level extras-to-package mapping, so the `optional:<extra>` selector is rejected. Use `pyproject.toml` if you need extras filtering.
- `pixi.lock` can mix PyPI and conda entries. Only PyPI entries are audited; conda entries are skipped with a warning showing the count.
- `pixi.lock` is also filtered to the host platform (plus `noarch`), matching how environment markers are evaluated for `uv.lock`.

## Environment markers track the host

Dependency markers (platform, Python version, extras) are evaluated against the current runtime. Dependencies that are conditional on a different platform or Python version aren't included.

## A C toolchain may be needed for some dependencies

Analyzing a dependency file or project directory downloads wheels and (when no wheel is published for a package) builds the source distribution into a wheel via PEP 517 isolated builds. Most of PyPI ships pre-built wheels, but for the small minority that don't (and that contain C extensions) `pip wheel` will need a working C toolchain (e.g. `build-essential` on Linux, the Xcode Command Line Tools on macOS, Visual Studio Build Tools on Windows). When the build fails, license-audit logs a warning and continues; that package's license info will be unavailable until you supply a `[tool.license-audit.overrides]` entry or install the toolchain. Direct venv and current-environment analysis aren't affected.

## Not legal advice

The output is informational, based on OSADL data. Real license compatibility depends on how you distribute, how you link, and what jurisdiction you're in. Treat anything this tool generates as a starting point for legal review, not the final answer.
