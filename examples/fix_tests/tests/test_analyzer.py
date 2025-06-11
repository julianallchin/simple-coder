import pytest
from analyzer.text_utils import clean_text, count_characters
from analyzer.word_counter import count_words_simple, count_words_advanced

def test_clean_text():
    assert clean_text("Hello, World!") == "hello world"
    assert clean_text("  Test  123.  ") == "  test  123  " # note: re.sub keeps internal spaces

def test_count_characters():
    assert count_characters("hello") == 5
    assert count_characters("hello world") == 11
    assert count_characters("hello world", include_spaces=False) == 10

def test_count_words_simple():
    assert count_words_simple("one two three") == 3
    assert count_words_simple("  leading and trailing spaces  ") == 4
    assert count_words_simple("") == 0

def test_count_words_advanced_basic():
    text = "apple banana apple"
    expected = {"apple": 2, "banana": 1}
    assert count_words_advanced(text) == expected

def test_count_words_advanced_punctuation_and_case():
    text = "Apple, Banana! APPLE."
    expected = {"apple": 2, "banana": 1}
    assert count_words_advanced(text) == expected

def test_count_words_advanced_with_common_word():
    """
    This test is designed to fail due to the bug in count_words_advanced.
    """
    text = "The quick brown fox jumps over the lazy dog. The dog barks."
    # Expected counts WITHOUT the bug:
    # the: 3, quick: 1, brown: 1, fox: 1, jumps: 1, over: 1,
    # lazy: 1, dog: 2, barks: 1
    # The bug will make "the" count as 2 instead of 3.
    expected = {
        "the": 3, "quick": 1, "brown": 1, "fox": 1, "jumps": 1,
        "over": 1, "lazy": 1, "dog": 2, "barks": 1
    }
    assert count_words_advanced(text) == expected

def test_input_type_errors():
    with pytest.raises(TypeError):
        clean_text(123)
    with pytest.raises(TypeError):
        count_characters(None)
    with pytest.raises(TypeError):
        count_words_simple([1,2,3])
    with pytest.raises(TypeError):
        count_words_advanced(True)