# How it works

The pipeline runs in seven steps:

1. **Parse**: read the dependency specifier (`uv.lock`, `poetry.lock`, `pixi.lock`, `requirements.txt`, `pyproject.toml`, or an existing environment).
2. **Provision**: create a temporary environment with uv and install the dependencies. Skipped when analyzing a venv or the current environment directly.
3. **Detect**: walk `site-packages` and read each package's METADATA. Licenses come from PEP 639 `License-Expression`, the legacy `License` field, trove classifiers, or user overrides.
4. **Classify**: categorize each license as permissive, weak-copyleft, strong-copyleft, or network-copyleft using OSADL copyleft data.
5. **Analyze**: check pairwise compatibility using the OSADL matrix and flag conflicts. For OR expressions (e.g. `MIT OR GPL-2.0`), pick the most permissive alternative.
6. **Recommend**: determine the most permissive outbound license that satisfies every dependency constraint.
7. **Report**: render findings as terminal output, Markdown, JSON, or third-party notices.
