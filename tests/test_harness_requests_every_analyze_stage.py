"""The harness must ASK for every /analyze stage, and refuse a response that skipped one.

App service 1.7.0 made `/analyze`'s optional stages opt-in (`structured`,
`sections`, `rendered`, all default OFF). `scripts/harness/extract.py` called a
bare `/analyze?level=X`, so against that service it would have received
`sections`, `tables` and `rendered` as null. `_save_views` silently writes only
the views that arrive, so every Tier-D check reading `rendered.md` or
`tables.json` would have lost its input with nothing going red. Worse, a
`rendered.md` left over from an earlier run would have been read back as if this
run had produced it.

Three guarantees are pinned, each two-sided:
  1. the request names all three stages;
  2. a response that reports a requested stage as `skipped` raises, and a
     `computed` / `unsupported_format` response does not;
  3. a stale view file from a previous run does not survive a run that did not
     produce it.
"""
import io
import json

import pytest

from scripts.harness import extract as hx


def _analyze(stages: dict | None, *, rendered: str | None = "# md") -> dict:
    meta = {"docpluck_version": "x"}
    if stages is not None:
        meta["stages"] = stages
    return {
        "raw": {"text": "raw"},
        "normalized": {"text": "norm"},
        "rendered": {"markdown": rendered} if rendered is not None else None,
        "sections": [] if rendered is not None else None,
        "tables": [] if rendered is not None else None,
        "metadata": meta,
    }


ALL_COMPUTED = {"sections": "computed", "tables": "computed", "rendered": "computed"}


def test_request_names_every_optional_stage(monkeypatch, tmp_path):
    seen = {}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return _Resp(json.dumps(_analyze(ALL_COMPUTED)).encode("utf-8"))

    monkeypatch.setattr(hx.urllib.request, "urlopen", fake_urlopen)
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    hx._post_analyze("http://127.0.0.1:6117", "tok", pdf, "academic", 5)

    url = seen["url"]
    for flag in ("structured=true", "sections=true", "rendered=true", "level=academic"):
        assert flag in url, f"{flag!r} missing from {url!r}"


def test_a_skipped_requested_stage_raises(tmp_path):
    stages = dict(ALL_COMPUTED, rendered="skipped")
    with pytest.raises(RuntimeError, match="rendered"):
        hx._save_views(tmp_path, _analyze(stages, rendered=None))


@pytest.mark.parametrize(
    "stages",
    [
        ALL_COMPUTED,
        # DOCX/HTML: PDF-only stages are legitimately unsupported, not skipped.
        {"sections": "computed", "tables": "unsupported_format", "rendered": "unsupported_format"},
        # A pre-1.7.0 service reports no stages at all and computes everything.
        None,
    ],
)
def test_computed_or_unsupported_does_not_raise(tmp_path, stages):
    written = hx._save_views(tmp_path, _analyze(stages))
    assert "raw.txt" in written


def test_a_stale_view_does_not_survive_a_run_that_did_not_produce_it(tmp_path):
    (tmp_path / "rendered.md").write_text("STALE from an earlier run", encoding="utf-8")
    written = hx._save_views(
        tmp_path,
        _analyze(
            {"sections": "computed", "tables": "unsupported_format", "rendered": "unsupported_format"},
            rendered=None,
        ),
    )
    assert "rendered.md" not in written
    assert not (tmp_path / "rendered.md").exists()


def test_control_a_view_that_was_produced_is_written(tmp_path):
    (tmp_path / "rendered.md").write_text("STALE", encoding="utf-8")
    hx._save_views(tmp_path, _analyze(ALL_COMPUTED, rendered="# fresh"))
    assert (tmp_path / "rendered.md").read_text(encoding="utf-8") == "# fresh"
