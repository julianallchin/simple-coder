import re

def clean_text(text: str) -> str:
    """Removes punctuation and converts text to lowercase."""
    if not isinstance(text, str):
        raise TypeError("Input must be a string.")
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text) # Keep words and whitespace
    return text

def count_characters(text: str, include_spaces: bool = True) -> int:
    """Counts characters in a string."""
    if not isinstance(text, str):
        raise TypeError("Input must be a string.")
    if not include_spaces:
        return len(text.replace(" ", ""))
    return len(text)