from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _extract_python_versions_from_workflow(text: str) -> list[str]:
    m = re.search(r'python-version:\s*\[([^\]]+)\]', text)
    if not m:
        raise ValueError("Could not find python-version matrix in workflow")
    raw = m.group(1)
    return re.findall(r'"(\d+\.\d+)"', raw)


def _extract_python_versions_from_pyproject(text: str) -> list[str]:
    return re.findall(r'Programming Language :: Python :: (\d+\.\d+)', text)


def main() -> int:
    normalize_py = _read("docpluck/normalize.py")
    docs_readme = _read("docs/README.md")
    docs_normalization = _read("docs/NORMALIZATION.md")
    docs_benchmarks = _read("docs/BENCHMARKS.md")
    pyproject = _read("pyproject.toml")
    workflow = _read(".github/workflows/test.yml")

    m = re.search(r'NORMALIZATION_VERSION\s*=\s*"([^"]+)"', normalize_py)
    if not m:
        raise AssertionError("NORMALIZATION_VERSION not found in docpluck/normalize.py")
    norm_version = m.group(1)

    if norm_version not in docs_readme:
        raise AssertionError(
            f"docs/README.md must mention current normalization version {norm_version}"
        )

    if "NORMALIZATION_VERSION" not in docs_normalization:
        raise AssertionError(
            "docs/NORMALIZATION.md must reference NORMALIZATION_VERSION as source of truth"
        )

    workflow_versions = _extract_python_versions_from_workflow(workflow)
    pyproject_versions = _extract_python_versions_from_pyproject(pyproject)
    if sorted(workflow_versions) != sorted(pyproject_versions):
        raise AssertionError(
            "Python versions mismatch between workflow matrix and pyproject classifiers: "
            f"workflow={workflow_versions}, pyproject={pyproject_versions}"
        )

    min_v = min(workflow_versions, key=lambda v: tuple(map(int, v.split("."))))
    max_v = max(workflow_versions, key=lambda v: tuple(map(int, v.split("."))))
    bench_range = f"Python {min_v}-{max_v}"
    if bench_range not in docs_benchmarks:
        raise AssertionError(
            f"docs/BENCHMARKS.md must contain '{bench_range}' in test-suite section"
        )

    print("docs/code consistency checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

