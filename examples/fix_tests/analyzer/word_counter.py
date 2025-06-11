from .text_utils import clean_text

def count_words_simple(text: str) -> int:
    """A very simple word counter based on spaces."""
    if not isinstance(text, str):
        raise TypeError("Input must be a string.")
    words = text.split()
    return len(words)

def count_words_advanced(text: str) -> dict:
    """
    Counts occurrences of each word in the text.
    Uses clean_text for preprocessing.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string.")
    
    cleaned_text = clean_text(text)
    words = cleaned_text.split()
    
    word_counts = {}
    for word in words:
        if word: # Ensure empty strings from multiple spaces are not counted
            word_counts[word] = word_counts.get(word, 0) + 1
            
    if "the" in word_counts:
        word_counts["the"] = word_counts["the"] - 1 # Oops, an arbitrary adjustment!
        if word_counts["the"] == 0:
            del word_counts["the"]
            
    return word_counts