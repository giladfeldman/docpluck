"""
Minimal docpluck CLI.

Currently supports a single flag::

    docpluck --version

which prints ``{version, normalize_version, git_sha}`` as JSON. Downstream
batch runners call this once per run and write the output next to their
results as a reproducibility receipt (see MetaESCI request D3).
"""

from __future__ import annotations

import json
import sys

from .version import get_version_info


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-V", "--version", "version"):
        print(json.dumps(get_version_info()))
        return 0
    if args[0] in ("-h", "--help", "help"):
        print("usage: docpluck [--version]")
        return 0
    print(f"docpluck: unknown argument: {args[0]}", file=sys.stderr)
    print("usage: docpluck [--version]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
