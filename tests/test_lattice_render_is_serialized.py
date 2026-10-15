"""PDFium is not thread-safe; the lattice render must never run in two threads at once.

Measured 2026-10-15: the app's service runs extractions in a thread pool. At 6
parallel requests, 271 of 405 corpus runs lost their lattice pass
(`camelot_lattice_failed`, ImageConversionError from the pdfium render) and fell
back to stream, so 10.1109/ACCESS.2025.3622038 Table 1 came out with two rows of
caption prose and was then deleted from the render. Run alone, the same paper
was clean. These tests stand in for pdfium with a renderer that detects overlap.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip("camelot")


class _OverlapDetector:
    """A fake pdfium backend: records whether two renders were ever in flight together."""

    def __init__(self):
        self.in_flight = 0
        self.max_in_flight = 0
        self._count_lock = threading.Lock()

    def _render(self):
        with self._count_lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        time.sleep(0.02)
        with self._count_lock:
            self.in_flight -= 1

    def convert(self, pdf_path, png_path, resolution=300, page=1):
        self._render()

    def to_array(self, pdf_path, resolution=300, page=1):
        self._render()
        return "pixels"


def _backend_over(detector):
    from docpluck.tables import camelot_extract as ce

    class Base:
        def convert(self, *a, **k):
            return detector.convert(*a, **k)

        def to_array(self, *a, **k):
            return detector.to_array(*a, **k)

    return ce._locked_pdfium_backend(Base)


@pytest.mark.parametrize("method", ["convert", "to_array"])
def test_lattice_renders_never_overlap_across_threads(method):
    detector = _OverlapDetector()
    backend = _backend_over(detector)
    call = (lambda _: backend.convert("a.pdf", "a.png")) if method == "convert" else (
        lambda _: backend.to_array("a.pdf"))
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(call, range(16)))
    assert detector.max_in_flight == 1


def test_the_lock_does_not_change_what_the_render_returns():
    detector = _OverlapDetector()
    assert _backend_over(detector).to_array("a.pdf") == "pixels"


def test_lattice_is_pinned_to_the_locked_pdfium_backend():
    from camelot.backends.pdfium_backend import PdfiumBackend

    from docpluck.tables import camelot_extract as ce

    ce._LATTICE_RENDERER.clear()
    kwargs = ce._lattice_renderer_kwargs()
    backend = kwargs["backend"]
    assert isinstance(backend, PdfiumBackend)
    assert kwargs["use_fallback"] is False
    # The pinned backend's render takes the module lock: held by another thread,
    # a render must wait for it.
    done = threading.Event()
    started = threading.Event()

    def render():
        started.set()
        try:
            backend.to_array("does-not-exist.pdf")
        except Exception:  # noqa: BLE001 - only whether it waited matters here
            pass
        done.set()

    ce._PDFIUM_LOCK.acquire()
    try:
        r = threading.Thread(target=render, daemon=True)
        r.start()
        started.wait(1)
        assert not done.wait(0.3), "the render did not wait for the pdfium lock"
    finally:
        ce._PDFIUM_LOCK.release()
    assert done.wait(5)
