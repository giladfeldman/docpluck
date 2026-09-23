"""Extraction driver for the docpluck verification harness.

Drives the *local app* — the FastAPI extraction service the deployed product
uses — over HTTP, exactly as the frontend does. For every corpus document ×
every normalization level it calls ``/analyze`` and saves every output view to
disk, so verification inspects *the artifact the user downloads*, not an
internal library call.

Why the app and not ``render_pdf_to_markdown`` directly: the 2026-05-17
post-mortem found defects living in the app↔library gap (stale pins, caches,
level defaults) that a library-only test cannot see. See
``an internal iteration doc``.

Idempotent + resumable: a document whose source bytes and the service's
docpluck version are unchanged is skipped unless ``--force``. An errored
document is recorded and the run continues.

Usage::

    python -m scripts.harness.extract                 # whole corpus, 3 levels
    python -m scripts.harness.extract --only <doc_id> --levels academic
    python -m scripts.harness.extract --source escicheck --workers 4
"""

from __future__ import annotations

import argparse
import concurrent.futures as _cf
import datetime as _dt
import hashlib
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from . import corpus

LEVELS = ("none", "standard", "academic")
# ONE definition, in `corpus`, and it points OUTSIDE this repo.
# See `corpus._out_root`: this used to be `<repo>/verify_out`, declared
# identically in three modules, and it held 347 MB of rendered publication
# text inside the working tree. Custody rule: article-finder is the sole
# custodian, and gitignoring is not containment.
OUT_ROOT = corpus.OUT_ROOT

# The local FastAPI extraction service. The service URL + internal token live
# in the app repo's env files; read them so the harness never hard-codes a
# secret and tracks whatever the app is actually configured with.
# Located STRUCTURALLY, never by name -- this repo is PUBLIC and a hardcoded
# sibling name publishes the private consumer's layout. `default_app_repo()` in
# `scripts/check_app_pin_sync.py` already solves exactly this (it looks for a
# sibling holding a `service/requirements.txt` with a docpluck pin) and is the
# single definition of that convention; duplicating it here is how two copies
# drift. $DOCPLUCK_APP_REPO overrides.
def _app_repo() -> Path | None:
    try:
        from scripts.check_app_pin_sync import default_app_repo
    except ImportError:  # invoked outside the package -- fall back to the env var
        override = os.environ.get("DOCPLUCK_APP_REPO")
        return Path(override).expanduser().resolve() if override else None
    return default_app_repo()


def _read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def service_config() -> tuple[str, str]:
    """(base_url, internal_token) for the local extraction service."""
    app = _app_repo()
    fe = _read_env(app / "frontend" / ".env.local") if app else {}
    sv = _read_env(app / "service" / ".env") if app else {}
    url = os.environ.get("EXTRACTION_SERVICE_URL") or fe.get(
        "EXTRACTION_SERVICE_URL", "http://localhost:6117"
    )
    token = (
        os.environ.get("INTERNAL_SERVICE_TOKEN")
        or sv.get("INTERNAL_SERVICE_TOKEN")
        or fe.get("INTERNAL_SERVICE_TOKEN", "")
    )
    url = _require_local_extraction(url.rstrip("/"))
    return url, token


def _require_local_extraction(url: str) -> str:
    """Refuse a non-loopback extraction service unless explicitly permitted.

    service_config() resolves EXTRACTION_SERVICE_URL from the environment AND
    from the app checkout's own frontend env file -- which carries the
    PRODUCTION URL.
    So this harness could reach the metered hosted service by default, with no
    guard anywhere on the path.

    Standing user directive: cross-testing is ALWAYS local unless the user
    approves otherwise; hosted extractions are metered and the user pays
    personally. Override with DOCPLUCK_ALLOW_REMOTE=1, deliberately loud.
    """
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host in ("127.0.0.1", "localhost", "0.0.0.0", "::1"):
        return url
    if os.environ.get("DOCPLUCK_ALLOW_REMOTE") == "1":
        print(f"[local-only] WARNING: extraction service is REMOTE ({url}). "
              f"This is metered and costs money.", flush=True)
        return url
    raise RuntimeError(
        f"EXTRACTION_SERVICE_URL resolves to {url!r}, which is NOT a local "
        f"service. Cross-testing must run against a LOCAL extraction service "
        f"(user directive); hosted calls are metered and the user pays "
        f"personally. Start the local app service on 127.0.0.1:6117, or set "
        f"DOCPLUCK_ALLOW_REMOTE=1 to override. Note the URL may come from "
        f"the app checkout's frontend env file, not from your shell."
    )


def service_health(base_url: str) -> dict:
    """GET /health — raises if the service is not reachable."""
    with urllib.request.urlopen(f"{base_url}/health", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _multipart(file_path: Path) -> tuple[bytes, str]:
    """Build a multipart/form-data body with a single ``file`` field."""
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    pre = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8")
    post = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = pre + file_path.read_bytes() + post
    return body, f"multipart/form-data; boundary={boundary}"


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    h.update(path.read_bytes())
    return h.hexdigest()


# Every optional /analyze stage, requested EXPLICITLY. Since app service 1.7.0
# these default OFF: a bare `/analyze?level=X` returns `sections`, `tables` and
# `rendered` as null, and `_save_views` would then write fewer views while every
# Tier-D check that reads them lost its input silently. A service older than
# 1.7.0 ignores the flags and computes everything anyway, so this is safe both
# ways.
_ANALYZE_STAGES = "structured=true&sections=true&rendered=true"
_REQUESTED_STAGES = ("sections", "tables", "rendered")


def _post_analyze(base_url: str, token: str, file_path: Path, level: str, timeout: int) -> dict:
    body, ctype = _multipart(file_path)
    req = urllib.request.Request(
        f"{base_url}/analyze?level={level}&{_ANALYZE_STAGES}",
        data=body,
        method="POST",
        headers={"Content-Type": ctype, "x-internal-service-token": token},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# View key in the /analyze response → (output filename, how to extract the text).
_TEXT_VIEWS = {
    "raw": ("raw.txt", lambda d: (d.get("raw") or {}).get("text", "")),
    "normalized": ("normalized.txt", lambda d: (d.get("normalized") or {}).get("text", "")),
    "rendered": ("rendered.md", lambda d: (d.get("rendered") or {}).get("markdown", "")),
}
_JSON_VIEWS = {
    "sections": ("sections.json", lambda d: d.get("sections")),
    "tables": ("tables.json", lambda d: d.get("tables")),
}


def _save_views(out_dir: Path, analyze: dict) -> list[str]:
    """Split the /analyze response into per-view files. Returns the views written.

    Refuses a response in which a stage this harness asked for was `skipped`:
    that is the service ignoring the request, and writing the views that did
    arrive would let the checks run over less than they think. Stale view files
    from an earlier run are removed first, so a view this run did not produce
    can never be read back as if it had.
    """
    stages = ((analyze.get("metadata") or {}).get("stages")) or {}
    skipped = sorted(s for s in _REQUESTED_STAGES if stages.get(s) == "skipped")
    if skipped:
        raise RuntimeError(
            f"/analyze skipped requested stage(s) {skipped}; metadata.stages={stages}"
        )
    for fname, _getter in (*_TEXT_VIEWS.values(), *_JSON_VIEWS.values()):
        (out_dir / fname).unlink(missing_ok=True)
    written: list[str] = []
    (out_dir / "analyze.json").write_text(
        json.dumps(analyze, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for _key, (fname, getter) in _TEXT_VIEWS.items():
        text = getter(analyze)
        if text:
            (out_dir / fname).write_text(text, encoding="utf-8")
            written.append(fname)
    for _key, (fname, getter) in _JSON_VIEWS.items():
        obj = getter(analyze)
        if obj is not None:
            (out_dir / fname).write_text(
                json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            written.append(fname)
    return written


def _process(
    doc: dict,
    level: str,
    cfg: tuple[str, str],
    *,
    force: bool,
    timeout: int,
    service_version: str | None = None,
) -> dict:
    """Extract one (document, level). Returns its _meta record."""
    base_url, token = cfg
    src = corpus.resolve(doc)
    out_dir = OUT_ROOT / doc["id"] / level
    meta_path = out_dir / "_meta.json"
    src_sha1 = _sha1(src) if src.is_file() else None

    if not force and meta_path.is_file():
        prev = json.loads(meta_path.read_text(encoding="utf-8"))
        if (
            prev.get("status") == "ok"
            and prev.get("source_sha1") == src_sha1
            # Extracted by the build the service is running RIGHT NOW. A bare
            # presence check here let outputs from an old library version be
            # skipped forever — the harness then "verified" a stale build
            # (false green, R-0004). No known version to compare against →
            # never skip.
            and prev.get("docpluck_version") is not None
            and service_version is not None
            and prev.get("docpluck_version") == service_version
        ):
            prev["skipped"] = True
            return prev

    out_dir.mkdir(parents=True, exist_ok=True)
    meta: dict = {
        "doc_id": doc["id"],
        "format": doc["format"],
        "level": level,
        # Where the source came from, WITHOUT a portfolio path: a manifest record
        # carries `corpus_path` (a custodian paper) or `sha256` (another source),
        # and since the 2026-09-17 repoint never `rel_path`. Reading `rel_path`
        # here raised KeyError outside the try below, so every extraction run
        # crashed on its first document.
        "source_ref": doc.get("corpus_path")
        or (f"{doc['source']}:{doc['sha256'][:16]}" if "sha256" in doc else doc.get("rel_path")),
        "source_sha1": src_sha1,
        "extracted_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "skipped": False,
    }
    if src_sha1 is None:
        meta.update(status="missing_source", error=f"source not found: {src}")
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return meta

    t0 = time.time()
    try:
        analyze = _post_analyze(base_url, token, src, level, timeout)
        meta["views"] = _save_views(out_dir, analyze)
        meta["status"] = "ok"
        meta["docpluck_version"] = (analyze.get("metadata") or {}).get("docpluck_version")
        meta["service_total_ms"] = (analyze.get("metadata") or {}).get(
            "total_extraction_time_ms"
        )
    except urllib.error.HTTPError as e:
        meta.update(status="http_error", http_code=e.code, error=e.read().decode("utf-8", "replace")[:500])
    except Exception as e:  # noqa: BLE001 — record any failure, keep the run going
        meta.update(status="error", error=f"{type(e).__name__}: {e}")
    meta["wall_seconds"] = round(time.time() - t0, 1)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def run(
    docs: list[dict],
    levels: tuple[str, ...],
    *,
    force: bool = False,
    workers: int = 1,
    timeout: int = 900,  # see argparse default below — Camelot-heavy papers need >300s
) -> list[dict]:
    cfg = service_config()
    health = service_health(cfg[0])
    service_version = health.get("docpluck_version")
    print(
        f"service {cfg[0]} · docpluck {service_version} · "
        f"{len(docs)} docs × {len(levels)} levels = {len(docs) * len(levels)} extractions"
    )
    jobs = [(d, lv) for d in docs for lv in levels]
    results: list[dict] = []
    done = 0
    if workers > 1:
        with _cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {
                ex.submit(
                    _process, d, lv, cfg,
                    force=force, timeout=timeout, service_version=service_version,
                ): (d, lv)
                for d, lv in jobs
            }
            for fut in _cf.as_completed(futs):
                m = fut.result()
                results.append(m)
                done += 1
                _log(done, len(jobs), m)
    else:
        for d, lv in jobs:
            m = _process(d, lv, cfg, force=force, timeout=timeout, service_version=service_version)
            results.append(m)
            done += 1
            _log(done, len(jobs), m)
    ok = sum(1 for m in results if m["status"] == "ok")
    skipped = sum(1 for m in results if m.get("skipped"))
    failed = [m for m in results if m["status"] != "ok"]
    print(f"\ndone: {ok} ok ({skipped} skipped), {len(failed)} failed")
    for m in failed:
        print(f"  FAIL {m['doc_id']}/{m['level']}: {m['status']} — {m.get('error','')[:120]}")
    return results


def _log(done: int, total: int, m: dict) -> None:
    tag = "skip" if m.get("skipped") else ("ok" if m["status"] == "ok" else "FAIL")
    print(f"[{done}/{total}] {tag:4s} {m['doc_id']}/{m['level']}", flush=True)


def _filter(manifest: dict, args: argparse.Namespace) -> list[dict]:
    docs = manifest["documents"]
    if args.format:
        docs = [d for d in docs if d["format"] in args.format]
    if args.source:
        docs = [d for d in docs if d["source"] in args.source]
    if args.only:
        wanted = set(args.only)
        docs = [d for d in docs if d["id"] in wanted]
    if args.limit:
        docs = docs[: args.limit]
    return docs


def main() -> int:
    ap = argparse.ArgumentParser(description="docpluck harness — extraction driver")
    ap.add_argument("--levels", nargs="+", choices=LEVELS, default=list(LEVELS))
    ap.add_argument("--format", nargs="+", choices=["pdf", "docx", "html"])
    ap.add_argument("--source", nargs="+")
    ap.add_argument("--only", nargs="+", help="specific doc ids")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true", help="re-extract even if unchanged")
    ap.add_argument("--workers", type=int, default=1)
    # Default 900s (15 min): Camelot-heavy papers — nat-comms-3, xiao-poc-epley
    # — legitimately need 600-1200s of table extraction work. The previous 300s
    # default manufactured persistent false-FAILs on every full-corpus run (the
    # 2026-05-20 handoff chased these for two sessions as if they were code
    # bugs; they were always just the timeout being too tight). Cycle 10
    # follow-up: keep `--workers 2` recommended for big runs but stop forcing
    # users to know the right `--timeout 1200` invocation.
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    manifest = corpus.load_manifest()
    docs = _filter(manifest, args)
    if not docs:
        print("no documents matched the filter")
        return 1
    results = run(
        docs, tuple(args.levels), force=args.force, workers=args.workers, timeout=args.timeout
    )
    return 0 if all(m["status"] == "ok" for m in results) else 2


if __name__ == "__main__":
    sys.exit(main())
