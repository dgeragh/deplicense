# How it works

The pipeline runs in seven steps:

1. **Parse**: read the dependency specifier (`uv.lock`, `poetry.lock`, `pixi.lock`, `requirements.txt`, `pyproject.toml`, or an existing environment).
2. **Provision**: download wheels (building sdists when needed, via PEP 517) into a temporary directory using `pip wheel`. Skipped when analyzing a venv or the current environment directly; those paths read the existing site-packages.
3. **Detect**: read each package's METADATA, either from `.whl` archives (temp path) or from installed `*.dist-info/METADATA` files (venv paths). Licenses come from PEP 639 `License-Expression`, the legacy `License` field, trove classifiers, or user overrides.
4. **Classify**: categorize each license as permissive, weak-copyleft, strong-copyleft, or network-copyleft using OSADL copyleft data.
5. **Analyze**: check pairwise compatibility using the OSADL matrix and flag conflicts.
6. **Recommend**: determine the most permissive outbound license that satisfies every dependency constraint. For OR expressions (e.g. `MIT OR GPL-2.0`), the most permissive alternative is selected before constraint solving.
7. **Report**: render findings as terminal output, Markdown, JSON, or third-party notices.
