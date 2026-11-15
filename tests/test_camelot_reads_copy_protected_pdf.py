"""A copy-protected PDF with an empty user password reaches Camelot decrypted.

Before 2026-11-13 Camelot's pdfminer raised PDFTextExtractionNotAllowed on such a
PDF and the paper lost every table (10.1016/j.evolhumbehav.2014.02.004: tables
0 -> Table 2's 48 M/SD values, checked against the rasterized page 28). The
end-to-end case needs that paper; these pin the mechanism on generated PDFs.
"""
from __future__ import annotations

import io

import pypdf

from docpluck.tables.camelot_extract import _camelot_input_bytes
from docpluck.telemetry import fallback_scope


def _pdf(user: str | None) -> bytes:
    w = pypdf.PdfWriter()
    w.add_blank_page(width=200, height=200)
    if user is not None:
        # print allowed, copy/extract not -- the shape of the measured paper
        w.encrypt(user_password=user, owner_password="owner-secret",
                  permissions_flag=pypdf.constants.UserAccessPermissions.PRINT,
                  algorithm="AES-256")
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_empty_user_password_is_decrypted_for_camelot():
    src = _pdf("")
    assert pypdf.PdfReader(io.BytesIO(src)).is_encrypted
    with fallback_scope() as fb:
        out = _camelot_input_bytes(src)
    assert not pypdf.PdfReader(io.BytesIO(out)).is_encrypted
    assert fb.counters.get("camelot_input_decrypted_empty_password") == 1


def test_real_password_is_left_and_said():
    with fallback_scope() as fb:
        out = _camelot_input_bytes(_pdf("needs-this"))
    assert pypdf.PdfReader(io.BytesIO(out)).is_encrypted
    assert fb.counters.get("camelot_input_encrypted_needs_password") == 1


def test_plain_pdf_untouched_and_silent():
    src = _pdf(None)
    with fallback_scope() as fb:
        out = _camelot_input_bytes(src)
    assert out == src
    assert not fb.counters


def test_glyph_repair_reads_the_decrypted_copy(monkeypatch):
    """Consult round 2 (Sonnet, 2026-11-13): the glyph-name repair ran on the
    still-encrypted bytes, before decryption. pypdf reads an empty-password
    file's fonts anyway, so this pins the order, not a reproduced wrong value.
    Failed on v2.4.160."""
    from docpluck.tables import camelot_extract as ce

    seen = []

    def spy(data):
        seen.append(pypdf.PdfReader(io.BytesIO(data)).is_encrypted)
        return data, None

    monkeypatch.setattr(ce, "repair_glyph_names", spy)
    ce._camelot_input_bytes(_pdf(""))
    assert seen == [False]
