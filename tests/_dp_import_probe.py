"""Helper for ``test_harness_scripts_import_the_working_tree.py``.

Run as::

    python tests/_dp_import_probe.py <script> <script-dir>

Executes ``<script>`` exactly as ``python <script>`` would -- including putting
``<script-dir>`` at ``sys.path[0]``, which is the whole defect under test -- and
prints ``RESOLVED::<path>`` naming the ``docpluck/__init__.py`` that the
script's own import would load.  Execution stops at that instant; nothing the
script does afterwards runs.

Not named ``test_*`` on purpose: it is a helper, not a test.
"""

from __future__ import annotations

import argparse
import importlib.abc
import importlib.util
import runpy
import sys

SCRIPT, SCRIPT_DIR = sys.argv[1], sys.argv[2]

# Python puts the SCRIPT'S OWN DIRECTORY -- never the cwd -- at sys.path[0].
sys.path[0] = SCRIPT_DIR

# Some scripts parse arguments at module level AND READ THEM before importing
# docpluck.  The probe is not exercising any CLI, so neutralise argument parsing
# rather than invent argv per script -- but an EMPTY Namespace is not enough:
# four scripts raised AttributeError on their own options and were scored as
# defective when the probe, not the script, had failed.  Answer any attribute
# with a value that tolerates the usual follow-on operations.
class _Anything:
    def __getattr__(self, _name):
        return self

    def __call__(self, *a, **k):
        return self

    def __getitem__(self, _k):
        return self

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __str__(self):
        return ""

    def __fspath__(self):
        return ""


argparse.ArgumentParser.parse_args = lambda self, *a, **k: _Anything()


class _Reporter(importlib.abc.MetaPathFinder):
    # Report where docpluck resolves, then stop before the script does work.
    def find_spec(self, name, path=None, target=None):
        if name != "docpluck":
            return None
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec("docpluck")
        print("RESOLVED::" + (spec.origin or "<none>"))
        raise SystemExit(0)


sys.meta_path.insert(0, _Reporter())
try:
    runpy.run_path(SCRIPT, run_name="__main__")
except BaseException:
    pass

# The script may exit, or fail on real work, before it ever reaches its own
# ``import docpluck`` -- two scripts do exactly that.  The question is still
# answerable: ask where docpluck WOULD resolve on the ``sys.path`` the script
# has left behind, which is precisely what its own import would have seen.
# Without this, a script that exits early is scored "measurement failed" and is
# indistinguishable from one that is genuinely broken.
spec = importlib.util.find_spec("docpluck")
print("RESOLVED::" + ((spec.origin if spec else None) or "<none>"))
