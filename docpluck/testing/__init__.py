"""Test-support helpers that BOTH repos import, so there is only one of each.

Nothing in here is imported by the extraction pipeline; it exists so the
library's own suite and the service's suite resolve the same corpus the same
way. A second copy of a resolver rots -- the two suites would then disagree
about which papers "the corpus" contains, silently, and each would still be
green.
"""

from docpluck.testing._root import (
    article_finder_home,
    project_skills_dir,
    tool_problem,
)
from docpluck.testing.corpus import (
    CorpusPaperMissing,
    corpus_available,
    corpus_names,
    corpus_pdf,
    corpus_pdfs,
    custody_path,
    repository_root,
    require_corpus_pdf,
    root_problem,
    verify_manifest,
)

__all__ = [
    "CorpusPaperMissing",
    "article_finder_home",
    "corpus_available",
    "corpus_names",
    "corpus_pdf",
    "corpus_pdfs",
    "custody_path",
    "project_skills_dir",
    "repository_root",
    "require_corpus_pdf",
    "root_problem",
    "tool_problem",
    "verify_manifest",
]
