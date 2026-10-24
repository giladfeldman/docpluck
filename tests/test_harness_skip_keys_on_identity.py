"""The harness reuses an earlier output only when the SAME build produced it.

The skip check compared the version string alone. While a version is unreleased its
number stays fixed across many commits, so an output from an earlier commit of that
version was skipped as current and the harness then checked an older build than the
one running. The key is now the service's full identity (version/sha/state), and a
dirty working tree never reuses anything, because it can change without its identity
changing.
"""
import inspect

from scripts.harness import extract as hx

OK = {"status": "ok", "source_sha1": "s"}


def test_same_version_from_another_commit_is_not_current():
    prev = {**OK, "docpluck_version": "9.9.9", "docpluck_identity": "9.9.9/aaaaaaa/clean"}
    assert not hx._is_current(prev, "s", "9.9.9/bbbbbbb/clean")


def test_same_identity_on_a_clean_build_is_current():
    prev = {**OK, "docpluck_identity": "9.9.9/aaaaaaa/clean"}
    assert hx._is_current(prev, "s", "9.9.9/aaaaaaa/clean")


def test_a_dirty_tree_never_reuses_an_output():
    prev = {**OK, "docpluck_identity": "9.9.9/aaaaaaa/dirty"}
    assert not hx._is_current(prev, "s", "9.9.9/aaaaaaa/dirty")


def test_an_output_without_an_identity_is_never_current():
    assert not hx._is_current({**OK, "docpluck_version": "9.9.9"}, "s", "9.9.9/aaaaaaa/clean")
    assert not hx._is_current({**OK, "docpluck_identity": "9.9.9/a/clean"}, "s", None)


def test_changed_source_or_failed_run_is_not_current():
    prev = {**OK, "docpluck_identity": "9.9.9/a/clean"}
    assert not hx._is_current(prev, "other", "9.9.9/a/clean")
    assert not hx._is_current({**prev, "status": "error"}, "s", "9.9.9/a/clean")


def test_the_run_reads_the_identity_from_health_and_records_it():
    src = inspect.getsource(hx)
    assert 'health.get("docpluck_identity")' in src
    assert 'meta["docpluck_identity"]' in src
