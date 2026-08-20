from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _requires_python_floor(text: str) -> tuple[int, int]:
    """The declared minimum interpreter, e.g. ``requires-python = ">=3.10"``.

    This used to read the GitHub Actions test matrix. That workflow was deleted
    on 2026-08-20 (the portfolio does not use GitHub Actions), which left this
    script reading a file that no longer exists — so the check would have
    crashed rather than passed, but it was ALSO the only thing pinning the
    classifier list to reality. Repointed at `requires-python`, which is the
    actual declaration and cannot silently disappear.
    """
    m = re.search(r'requires-python\s*=\s*"[><=~^]*(\d+)\.(\d+)"', text)
    if not m:
        raise ValueError("Could not find requires-python in pyproject.toml")
    return int(m.group(1)), int(m.group(2))


def _extract_python_versions_from_pyproject(text: str) -> list[str]:
    return re.findall(r'Programming Language :: Python :: (\d+\.\d+)', text)


def main() -> int:
    normalize_py = _read("docpluck/normalize.py")
    docs_readme = _read("docs/README.md")
    docs_normalization = _read("docs/NORMALIZATION.md")
    docs_benchmarks = _read("docs/BENCHMARKS.md")
    pyproject = _read("pyproject.toml")

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

    pyproject_versions = _extract_python_versions_from_pyproject(pyproject)
    if not pyproject_versions:
        raise AssertionError("pyproject.toml declares no Python version classifiers")

    floor = _requires_python_floor(pyproject)
    tuples = sorted(tuple(map(int, v.split("."))) for v in pyproject_versions)
    if tuples[0] != floor:
        raise AssertionError(
            "the lowest Python classifier must equal requires-python: "
            f"classifiers start at {tuples[0]}, requires-python says {floor}"
        )
    expected = [(floor[0], floor[1] + i) for i in range(len(tuples))]
    if tuples != expected:
        raise AssertionError(
            "Python version classifiers must be a contiguous range from "
            f"requires-python: got {pyproject_versions}"
        )

    min_v = ".".join(map(str, tuples[0]))
    max_v = ".".join(map(str, tuples[-1]))
    bench_range = f"Python {min_v}-{max_v}"
    if bench_range not in docs_benchmarks:
        raise AssertionError(
            f"docs/BENCHMARKS.md must contain '{bench_range}' in test-suite section"
        )

    print("docs/code consistency checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

