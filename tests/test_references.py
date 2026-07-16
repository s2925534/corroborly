import pytest

from ledgerly.engine.references import (
    CITATION_STYLES,
    apa7_reference,
    chicago_reference,
    format_inline_citation,
    format_reference,
    ieee_reference,
    mla_reference,
)


def _metadata(**overrides):
    base = {
        "authors": ["Doe, J."],
        "year": 2023,
        "title": "A Study of Things",
        "publication_venue": "Journal of Studies",
        "doi": "10.1234/example",
    }
    base.update(overrides)
    return base


def test_apa7_reference_unchanged_format():
    assert apa7_reference(_metadata()) == (
        "Doe, J. (2023). A Study of Things. Journal of Studies. https://doi.org/10.1234/example"
    )


def test_mla_reference_format():
    reference = mla_reference(_metadata())
    assert reference.startswith('Doe, J.. "A Study of Things."')
    assert "Journal of Studies," in reference
    assert reference.endswith("2023. https://doi.org/10.1234/example")


def test_chicago_reference_format():
    reference = chicago_reference(_metadata())
    assert reference.startswith('Doe, J.. 2023. "A Study of Things."')


def test_ieee_reference_format_with_number():
    reference = ieee_reference(_metadata(), number=3)
    assert reference.startswith('[3] Doe, J., "A Study of Things,"')


def test_ieee_reference_format_without_number_has_no_bracket_prefix():
    reference = ieee_reference(_metadata())
    assert not reference.startswith("[")


def test_format_reference_dispatches_by_style():
    assert format_reference(_metadata(), "apa7") == apa7_reference(_metadata())
    assert format_reference(_metadata(), "mla") == mla_reference(_metadata())
    assert format_reference(_metadata(), "chicago") == chicago_reference(_metadata())
    assert format_reference(_metadata(), "ieee", number=1) == ieee_reference(_metadata(), number=1)


def test_format_reference_rejects_unknown_style():
    with pytest.raises(ValueError, match="Unknown citation style"):
        format_reference(_metadata(), "harvard")


def test_format_inline_citation_apa_style():
    assert format_inline_citation(_metadata(), "apa7") == "(Doe, 2023)"


def test_format_inline_citation_mla_style_omits_year():
    assert format_inline_citation(_metadata(), "mla") == "(Doe)"


def test_format_inline_citation_chicago_style():
    assert format_inline_citation(_metadata(), "chicago") == "(Doe 2023)"


def test_format_inline_citation_ieee_style_uses_number():
    assert format_inline_citation(_metadata(), "ieee", number=2) == "[2]"


def test_format_inline_citation_ieee_style_without_number_is_placeholder():
    assert format_inline_citation(_metadata(), "ieee") == "[?]"


def test_format_inline_citation_rejects_unknown_style():
    with pytest.raises(ValueError, match="Unknown citation style"):
        format_inline_citation(_metadata(), "harvard")


def test_citation_styles_set_has_exactly_four_entries():
    assert CITATION_STYLES == {"apa7", "mla", "chicago", "ieee"}


def test_reference_functions_never_fabricate_missing_metadata():
    empty = {"authors": None, "year": None, "title": None, "publication_venue": None, "doi": None}
    for style_fn in (apa7_reference, mla_reference, chicago_reference, ieee_reference):
        reference = style_fn(empty)
        assert "Unknown author" in reference
        assert "n.d." in reference
        assert "Unknown title" in reference
