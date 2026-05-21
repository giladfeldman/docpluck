"""Extraction driver for the docpluck verification harness.

Drives the *local app* — the FastAPI extraction service the deployed product
uses — over HTTP, exactly as the frontend does. For every corpus document ×
every normalization level it calls ``/analyze`` and saves every output view to
disk, so verification inspects *the artifact the user downloads*, not an
internal library call.

Why the app and not ``render_pdf_to_markdown`` directly: the 2026-05-17
post-mortem found defects living in the app↔library gap (stale pins, caches,
level defaults) that a library-only test cannot see. See
``docs/ITERATION_VERIFICATION_LESSONS.md``.

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
import urllib.request
import uuid
from pathlib import Path

from . import corpus

LEVELS = ("none", "standard", "academic")
_REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = _REPO_ROOT / "verify_out"

# The local FastAPI extraction service. The service URL + internal token live
# in the app repo's env files; read them so the harness never hard-codes a
# secret and tracks whatever the app is actually configured with.
_APP_REPO = corpus.VIBE / "MetaScienceTools" / "PDFextractor"


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
    fe = _read_env(_APP_REPO / "frontend" / ".env.local")
    sv = _read_env(_APP_REPO / "service" / ".env")
    url = os.environ.get("EXTRACTION_SERVICE_URL") or fe.get(
        "EXTRACTION_SERVICE_URL", "http://localhost:6117"
    )
    token = (
        os.environ.get("INTERNAL_SERVICE_TOKEN")
        or sv.get("INTERNAL_SERVICE_TOKEN")
        or fe.get("INTERNAL_SERVICE_TOKEN", "")
    )
    return url.rstrip("/"), token


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


def _post_analyze(base_url: str, token: str, file_path: Path, level: str, timeout: int) -> dict:
    body, ctype = _multipart(file_path)
    req = urllib.request.Request(
        f"{base_url}/analyze?level={level}",
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
    """Split the /analyze response into per-view files. Returns the views written."""
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


def _process(doc: dict, level: str, cfg: tuple[str, str], *, force: bool, timeout: int) -> dict:
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
            and prev.get("docpluck_version")  # extracted by a known build
        ):
            prev["skipped"] = True
            return prev

    out_dir.mkdir(parents=True, exist_ok=True)
    meta: dict = {
        "doc_id": doc["id"],
        "format": doc["format"],
        "level": level,
        "rel_path": doc["rel_path"],
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
    print(
        f"service {cfg[0]} · docpluck {health.get('docpluck_version')} · "
        f"{len(docs)} docs × {len(levels)} levels = {len(docs) * len(levels)} extractions"
    )
    jobs = [(d, lv) for d in docs for lv in levels]
    results: list[dict] = []
    done = 0
    if workers > 1:
        with _cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {
                ex.submit(_process, d, lv, cfg, force=force, timeout=timeout): (d, lv)
                for d, lv in jobs
            }
            for fut in _cf.as_completed(futs):
                m = fut.result()
                results.append(m)
                done += 1
                _log(done, len(jobs), m)
    else:
        for d, lv in jobs:
            m = _process(d, lv, cfg, force=force, timeout=timeout)
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
