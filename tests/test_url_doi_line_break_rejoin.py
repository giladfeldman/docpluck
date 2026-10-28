"""A line break inside a URL or DOI is joined with no space.

pdftotext breaks a long URL wherever the line ends, so the text channel says
``https://doi.org/10.1126/science.a`` / ``ac4716``. S8 then joined the two lines
with a space (``science.a ac4716``) and so did every later line-join step: the
DOI no longer resolves. 10.1525/collabra.77608 cut 23 of its 51 reference DOIs
this way, the host included (``https://doi.or g/``, ``http s://``); pages
rasterized 2026-10-27.

The join is made only when the line ends in a URL/DOI token and the next line
opens with a token that can only be its continuation (a digit or inner
punctuation, no comma); a complete DOI followed by the next reference, a word,
a list number or a page number keeps its break.
"""
from __future__ import annotations

import pytest

from docpluck.normalize import NormalizationLevel, _rejoin_broken_urls, normalize_text


@pytest.mark.parametrize(
    "text, expected",
    [
        ("321-342. https://doi.org/10.1007/s40070-01\n8-0082-7\nBrandt, M. J.",
         "321-342. https://doi.org/10.1007/s40070-018-0082-7\nBrandt, M. J."),
        ("254-272. https://doi.or\ng/10.37708/psyct.v13i1.442\nChoi, H.",
         "254-272. https://doi.org/10.37708/psyct.v13i1.442\nChoi, H."),
        ("29-33. http\ns://doi.org/10.1016/j.yebeh.2010.10.005\nDickert",
         "29-33. https://doi.org/10.1016/j.yebeh.2010.10.005\nDickert"),
        ("365-380. https:\n//doi.org/10.1002/bdm.558\nBates, D.",
         "365-380. https://doi.org/10.1002/bdm.558\nBates, D."),
        ("283-292. https://doi.org/\n10.1111/ajpy.12151\nGamliel",
         "283-292. https://doi.org/10.1111/ajpy.12151\nGamliel"),
        ("1085-1096. https://doi.org/10.1111/\nj.1539-6924.1994.tb00080.x\nAndrade",
         "1085-1096. https://doi.org/10.1111/j.1539-6924.1994.tb00080.x\nAndrade"),
        ("https://doi.org/10.1126/science.a\nac4716\nPeters",
         "https://doi.org/10.1126/science.aac4716\nPeters"),
        ("https://doi.org/10.1016/j.joe\np.2016.02.011\nFagerlin",
         "https://doi.org/10.1016/j.joep.2016.02.011\nFagerlin"),
        ("513-523. https://doi.org/10.1037/0022-3514\n.45.3.513\nSiegrist",
         "513-523. https://doi.org/10.1037/0022-3514.45.3.513\nSiegrist"),
        ("2021;50(1):346-351. doi:10.1093/ije/\ndyaa260\n16. White H.",
         "2021;50(1):346-351. doi:10.1093/ije/dyaa260\n16. White H."),
        # a chain: the scheme and then the path break on consecutive lines
        ("13(1), 1-17. https:\n//doi.org/10.1002/(SICI)1099-0771(200001/03)13:1::AID-B\nDM333.3.0.CO;2-S\nFischhoff",
         "13(1), 1-17. https://doi.org/10.1002/(SICI)1099-0771(200001/03)13:1::AID-BDM333.3.0.CO;2-S\nFischhoff"),
        # the host cut before the resolver name
        ("26-40. https://\ndoi.org/10.1016/j.concog.2016.03.005\nNext",
         "26-40. https://doi.org/10.1016/j.concog.2016.03.005\nNext"),
        ("706-718. http://dx.\ndoi.org/10.1037/0022-3514.45.3.706\nNext",
         "706-718. http://dx.doi.org/10.1037/0022-3514.45.3.706\nNext"),
        ("Available from: http://\nwww.ncbi.nlm.nih.gov/pubmed/14511961.\nNext",
         "Available from: http://www.ncbi.nlm.nih.gov/pubmed/14511961.\nNext"),
        # a URL in prose: the continuation is followed by more words
        ("descriptions from the original study (https://\nosf.io/y97tp/). For example, in",
         "descriptions from the original study (https://osf.io/y97tp/). For example, in"),
    ],
)
def test_break_inside_a_url_is_joined_without_a_space(text, expected):
    assert _rejoin_broken_urls(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        # a complete DOI, then the next reference
        "39(2), 175-191. https://doi.org/10.3758/bf03193146\nFedorov, V., Mannino, F.",
        "754. doi:10.2337/dci19-0014\n3. Wilkinson MJ, Manoogian ENC",
        # the next entry of a numbered list, after a DOI that ends with a period
        "(2005), doi: 10.1371/journal.pmed.0020124.\n10. C. G. Begley, L. M. Ellis",
        # a URL that ends a clause, then a word
        "materials are on https://osf.io/fmuv2/\nand the data are on request",
        "materials: https://osf.io/fmuv2/\nStudy 2 replicated",
        # a page number below a blank line, and a page break
        "https://doi.org/10.1177/0013916508325892\n\n\f1247\n",
        "https://doi.org/10.1177/0013916508325892\n\f1247\n",
        # a URL closed by a bracket ends the token
        "(see https://osf.io/abc12)\n2.3 Procedure",
        # a section number after a URL
        "available at https://osf.io/abc12\n2.3. Procedure and design",
        # a real space after a DOI on one line stays
        "https://doi.org/10.1037/0022-3514.73.2.321 Next, we",
        # a word ending in http is not a scheme
        "the protocol is http\nsecure in practice",
        # two URLs on consecutive lines (10.1080/02699931.2024.2434156 ORCID ids)
        "http://orcid.org/0000-0002-7425-8421\nhttp://orcid.org/0000-0003-2812-6599",
        "https://osf.io/xwhu3\nhttps://osf.io/tfwrg",
        # a bare number below a web address (a footnote or page number),
        # 10.5465/amd.2023.0106
        "https://oecd.ai/en/vc\n3\nThe next paragraph",
        # counterexamples from the tier-2 consult (Sonnet, 2026-10-27):
        # a numbered heading or a bare number below a web address
        "Materials at https://osf.io/abc\n2.1\nMethods",
        # a letter-digit word opening the next sentence
        "Data: https://osf.io/ab12/\nH1 predicted a main effect",
        "Data: https://osf.io/ab12/\n2SLS estimates follow",
        # a second DOI on the next line, without a scheme
        "10.1016/j.x.2020.1\n10.1037/abc",
        "https://doi.org/10.1/a\ndoi.org/10.2/b",
        # whitespace-only lines (a bare form feed) on either side
        "\f\nhttps://doi.org/10.1111/ab12\n\f\n\x0b\n",
    ],
)
def test_a_complete_url_keeps_its_break(text):
    assert _rejoin_broken_urls(text) == text


def test_normalize_text_no_longer_spaces_a_broken_doi():
    text = (
        "References\n\n"
        "Peters, E. (2006). Numeracy and decision making. Psychological Science, 17(5), "
        "407-413. https://doi.org/10.1111/j.1467-9280.2006.01720.x\n"
        "Open Science Collaboration. (2015). Estimating the reproducibility of\n"
        "psychological science. Science, 349(6251). https://doi.org/10.1126/science.a\n"
        "ac4716\n"
        "Pachur, T. (2014). The affect gap. https://doi.or\n"
        "g/10.1037/dec0000006\n"
        "Smith, J. (2010). Title. https://doi.org/10.3758/bf03193146\n"
        "Fedorov, V., Mannino, F., & Zhang, R. (2009). Consequences.\n"
    )
    for level in (NormalizationLevel.standard, NormalizationLevel.academic):
        out, _ = normalize_text(text, level)
        assert "https://doi.org/10.1126/science.aac4716" in out, level
        assert "https://doi.org/10.1037/dec0000006" in out, level
        assert "bf03193146Fedorov" not in out, level
        assert "bf03193146 Fedorov" in out or "bf03193146\nFedorov" in out, level


def test_a7_does_not_glue_the_next_list_number_to_a_doi():
    text = (
        "References and Notes\n\n"
        "9. J. P. A. Ioannidis, Why most published research findings are false. PLoS Med. 2 "
        "(2005), doi: 10.1371/journal.pmed.0020124.\n"
        "10. C. G. Begley, L. M. Ellis, Raise standards for preclinical cancer research. "
        "Nature 483,\n531-533 (2012).\n"
    )
    out, _ = normalize_text(text, NormalizationLevel.academic)
    assert "0020124.10." not in out
    assert "0020124.\n10. C. G. Begley" in out


def test_a7_still_joins_a_doi_broken_after_a_dot():
    out, _ = normalize_text(
        "See Smith (doi:10.\n1007/s10683-020-09663-x) for details.\n",
        NormalizationLevel.academic,
    )
    assert "doi:10.1007/s10683-020-09663-x" in out


def test_collabra_77608_reference_dois_survive_the_render():
    from docpluck.render import render_pdf_to_markdown
    from docpluck.testing.corpus import custody_path

    p = custody_path("fulltext", "10.1525__collabra.77608.pdf")
    md = render_pdf_to_markdown(p.read_bytes())
    assert "https://doi.org/10.1126/science.aac4716" in md
    assert "https://doi.org/10.37708/psyct.v13i1.442" in md
    assert "https://doi.org/10.1016/j.yebeh.2010.10.005" in md
    assert "doi.or g/" not in md
    assert "http s://" not in md
    assert "https:// doi" not in md
    # `collabra.371` / `22` was a bare-integer line the pagination verdict
    # counted; joined, the verdict must still find and strip pages 5 and 22
    import re
    assert not re.search(r"^(?:5|22)$", md, re.M)
