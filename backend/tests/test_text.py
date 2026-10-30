import pytest

from orchestrai_review2.text import chunk_text, clean_text


def test_clean_text_collapses_whitespace_and_trims():
    assert clean_text("  A\tpaper\n\nwith   spaces.  ") == "A paper with spaces."


def test_chunk_text_preserves_configured_word_overlap():
    chunks = chunk_text("one two three four five six", chunk_size=4, overlap=2)

    assert chunks == ["one two three four", "three four five six"]


def test_chunk_text_handles_empty_and_short_input():
    assert chunk_text(" \n\t ") == []
    assert chunk_text("one two", chunk_size=4, overlap=1) == ["one two"]


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (3, -1), (3, 3)],
)
def test_chunk_text_rejects_invalid_chunk_configuration(chunk_size, overlap):
    with pytest.raises(ValueError):
        chunk_text("one two three", chunk_size=chunk_size, overlap=overlap)
