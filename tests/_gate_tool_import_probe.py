"""Import ONE gate tool in a fresh process and exit non-zero if it cannot load.

Kept as a file rather than a `-c` string so the code that runs is the code you can read,
and so a failure reports a real traceback with real line numbers.
Used by tests/test_gate_tools_named_by_skills_resolve.py.
"""

import importlib
import importlib.util
import sys
from pathlib import Path

rel = sys.argv[1]
repo = Path(__file__).resolve().parents[1]
# An operator runs these from the repo root, so the repo root is on sys.path there.
# Without this the package-import fallback fails for a reason that has nothing to do
# with the tool -- a false red is as useless as a false green.
sys.path.insert(0, str(repo))
path = repo / rel
spec = importlib.util.spec_from_file_location("gatetool", path)
module = importlib.util.module_from_spec(spec)
sys.modules["gatetool"] = module
try:
    spec.loader.exec_module(module)
except ImportError:
    # A module using relative imports must be loaded as part of its package -- which is
    # how its gate step invokes it (`scripts/harness/extract.py`).
    importlib.import_module(rel.removesuffix(".py").replace("/", "."))
