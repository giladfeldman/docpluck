"""Documentation-drift gate: the public surface in the CODE must appear in the DOCS.

    python scripts/check_docs_coverage.py            # surface + changelog + quickstart
    python scripts/check_docs_coverage.py --no-run   # skip executing the quickstart

Exit 0 = every public name is documented and the quickstart runs; exit 1 = drift, with
every missing item listed. Wired into `/docpluck-cleanup` (Section 1.0) and pinned
two-sided by `tests/test_docs_coverage_gate.py`.

WHY THIS EXISTS (2026-09-27). The GitHub README was 35 lines while the library had grown
to 38 public exports, three CLI subcommands and five environment switches; the fuller
guide in docs/README.md had drifted too -- 15 public functions and every output field were
undocumented, and it still described a pdfplumber fallback retired a week earlier. Nothing
failed, because nothing compared the docs with the code. This does, and the surface is
DERIVED from the code (`__all__`, dataclass / TypedDict fields, enum and Literal values,
function parameters, argparse calls, environment reads, pyproject extras) so a new export is
covered the moment it exists -- there is no hand-kept list here to forget to update.

"Documented" means: appears inside an inline code span or a fenced code block of
README.md or docs/README.md. Prose mentions do not count (the word "Table" in a sentence
is not documentation of the `Table` type).
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import inspect
import os
import re
import subprocess
import sys
import tempfile
import typing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = ("README.md", "docs/README.md")
QUICKSTART_HEADING = "## Quickstart"
# Read by the package but deliberately internal -- listed here WITH the reason, so an
# exemption is a visible decision and never a silent gap.
ENV_EXEMPT: dict[str, str] = {}


def _import_working_tree():
    # A script file puts ITS OWN directory on sys.path[0], so a bare `import docpluck`
    # would resolve an INSTALLED copy (see tests/test_harness_scripts_import_the_working_tree.py).
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import docpluck

    if Path(docpluck.__file__).resolve().parent != ROOT / "docpluck":
        raise SystemExit(f"imported docpluck from {docpluck.__file__}, not this tree")
    return docpluck


# --------------------------------------------------------------------------- surface
def _literal_values(tp) -> set[str]:
    out: set[str] = set()
    if typing.get_origin(tp) is typing.Literal:
        out |= {str(a) for a in typing.get_args(tp)}
    for a in typing.get_args(tp):
        out |= _literal_values(a)
    return out


def collect_surface() -> dict[str, set[str]]:
    """Every public token, grouped by kind, derived from the source."""
    dp = _import_working_tree()
    exports = set(dp.__all__)
    fields: set[str] = set()
    values: set[str] = set()
    params: set[str] = set()
    for name in dp.__all__:
        obj = getattr(dp, name)
        if inspect.isclass(obj) and issubclass(obj, enum.Enum):
            values |= {str(m.value) for m in obj}
        elif inspect.isclass(obj) and dataclasses.is_dataclass(obj):
            fields |= {f.name for f in dataclasses.fields(obj) if not f.name.startswith("_")}
        elif inspect.isclass(obj) and getattr(obj, "__annotations__", None):
            try:
                hints = typing.get_type_hints(obj)
            except Exception:
                hints = obj.__annotations__
            fields |= {k for k in hints if not k.startswith("_")}
            for tp in hints.values():
                values |= _literal_values(tp)
        elif inspect.isfunction(obj):
            for p in inspect.signature(obj).parameters.values():
                if not p.name.startswith("_"):
                    params.add(p.name)

    cli_src = (ROOT / "docpluck" / "cli.py").read_text(encoding="utf-8")
    subcommands, flags = set(), set()
    for node in ast.walk(ast.parse(cli_src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            first = node.args[0] if node.args else None
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            if node.func.attr == "add_parser":
                subcommands.add(first.value)
            elif node.func.attr == "add_argument" and first.value.startswith("--"):
                flags.add(first.value)
            elif node.func.attr == "add_argument":
                pass  # positional ("file"): named in the usage line, not a flag

    env: set[str] = set()
    env_re = re.compile(r"""(?:environ\.get|getenv|environ\[)\(?\s*["']([A-Z][A-Z0-9_]+)["']""")
    for py in (ROOT / "docpluck").rglob("*.py"):
        if "testing" in py.relative_to(ROOT / "docpluck").parts:
            continue  # test-corpus plumbing, not a user-facing switch
        env |= set(env_re.findall(py.read_text(encoding="utf-8")))
    env -= set(ENV_EXEMPT)

    try:
        import tomllib
    except ModuleNotFoundError:  # 3.10
        import tomli as tomllib
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = {f"[{k}]" for k in pyproject["project"].get("optional-dependencies", {})}

    return {
        "export": exports,
        "field": fields,
        "value": values,
        "parameter": params,
        "subcommand": subcommands,
        "cli flag": flags,
        "env var": env,
        "extra": extras,
    }


# --------------------------------------------------------------------------- docs
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
_INLINE_RE = re.compile(r"`([^`\n]+)`")


def documented_code_text(doc_files=DOC_FILES) -> str:
    chunks = []
    for rel in doc_files:
        text = (ROOT / rel).read_text(encoding="utf-8")
        chunks += _FENCE_RE.findall(text)
        chunks += _INLINE_RE.findall(_FENCE_RE.sub("", text))
    return "\n".join(chunks)


def _is_documented(kind: str, token: str, code: str) -> bool:
    if kind == "subcommand":
        return re.search(rf"\bdocpluck\s+{re.escape(token)}\b", code) is not None
    if kind == "extra":
        return token in code
    return re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", code) is not None


def find_undocumented(surface: dict[str, set[str]], code: str) -> list[str]:
    return sorted(
        f"{kind}: {tok}"
        for kind, toks in surface.items()
        for tok in toks
        if not _is_documented(kind, tok, code)
    )


# --------------------------------------------------------------------------- changelog
def latest_changelog_section() -> tuple[str, str]:
    """(newest released version, its notes -- plus any `## [Unreleased]` notes above it)."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heads = list(re.finditer(r"^## \[([^\]]+)\]", text, re.M))
    released = [i for i, h in enumerate(heads) if h.group(1).lower() != "unreleased"]
    if not released:
        raise SystemExit("CHANGELOG.md has no '## [version]' heading")
    i = released[0]
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    return heads[i].group(1), text[heads[0].start():end]


def check_changelog(surface: dict[str, set[str]], code: str) -> list[str]:
    """The newest release's user-facing names must be in the docs, and versions must agree."""
    problems = []
    version, section = latest_changelog_section()
    pyproject_version = re.search(
        r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M
    ).group(1)
    if version != pyproject_version:
        problems.append(f"changelog: newest entry is {version}, pyproject says {pyproject_version}")
    for rel, pat in (("README.md", r"\(Version ([0-9][^)]*)\)"),
                     ("CITATION.cff", r"^version:\s*\"?([0-9][^\"\s]*)")):
        path = ROOT / rel
        m = re.search(pat, path.read_text(encoding="utf-8"), re.M) if path.exists() else None
        if not m:
            problems.append(f"citation: no version found in {rel}")
        elif m.group(1) != pyproject_version:
            problems.append(f"citation: {rel} cites {m.group(1)}, pyproject says {pyproject_version}")

    every = set().union(*surface.values())
    for tok in set(_INLINE_RE.findall(section)):
        tok = tok.strip()
        user_facing = (
            tok in every
            or re.fullmatch(r"DOCPLUCK_[A-Z0-9_]+", tok)
            or re.fullmatch(r"--[a-z][a-z0-9-]+", tok)
        )
        if user_facing and not _is_documented("x", tok, code):
            problems.append(f"changelog {version}: `{tok}` is named in the release notes but not in the docs")
    return sorted(problems)


# --------------------------------------------------------------------------- quickstart
def quickstart_blocks(readme: str | None = None) -> tuple[list[str], list[list[str]]]:
    text = readme if readme is not None else (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.find(QUICKSTART_HEADING)
    if start < 0:
        raise SystemExit(f"README.md has no '{QUICKSTART_HEADING}' section")
    nxt = text.find("\n## ", start + len(QUICKSTART_HEADING))
    body = text[start: nxt if nxt > 0 else len(text)]
    py, cli = [], []
    for m in re.finditer(r"```(\w*)\n(.*?)```", body, re.S):
        lang, code = m.group(1), m.group(2)
        if lang == "python":
            py.append(code)
        elif lang in ("bash", "sh", "powershell", "console", ""):
            cli += [ln.split()[1:] for ln in code.splitlines() if ln.startswith("docpluck ")]
    if not py:
        raise SystemExit("README quickstart has no python block -- nothing would be executed")
    return py, cli


def run_quickstart() -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from docs_sample_documents import write_samples

    py, cli = quickstart_blocks()
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        write_samples(tmp)
        for i, code in enumerate(py, 1):
            r = subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env,
                               capture_output=True, text=True, encoding="utf-8", timeout=900)
            if r.returncode != 0:
                problems.append(f"quickstart python block {i} exited {r.returncode}:\n{r.stderr[-1500:]}")
        for args in cli:
            r = subprocess.run([sys.executable, "-m", "docpluck", *args], cwd=tmp, env=env,
                               capture_output=True, text=True, encoding="utf-8", timeout=900)
            if r.returncode != 0 or not r.stdout.strip():
                problems.append(f"quickstart command `docpluck {' '.join(args)}` exited "
                                f"{r.returncode} with {len(r.stdout)} chars of output:\n{r.stderr[-800:]}")
    if not problems:
        print(f"quickstart: {len(py)} python block(s) and {len(cli)} command(s) ran OK")
    return problems


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    surface = collect_surface()
    if not surface["export"]:
        print("FAIL: derived an EMPTY public surface -- the instrument is broken, not the docs clean")
        return 1
    code = documented_code_text()
    problems = find_undocumented(surface, code)
    problems += check_changelog(surface, code)
    if "--no-run" not in argv:
        problems += run_quickstart()
    n = sum(len(v) for v in surface.values())
    if problems:
        print(f"FAIL: {len(problems)} documentation problem(s) against {n} public tokens:")
        for p in problems:
            print("  -", p)
        return 1
    print(f"OK: all {n} public tokens documented "
          f"({', '.join(f'{len(v)} {k}' for k, v in surface.items())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
