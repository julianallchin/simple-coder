from analyzer import text_utils, word_counter

def demonstrate_analyzer(sample_text):
    print(f"Original Text: '{sample_text}'")
    
    cleaned = text_utils.clean_text(sample_text)
    print(f"Cleaned Text: '{cleaned}'")
    
    char_count_spaces = text_utils.count_characters(sample_text)
    char_count_no_spaces = text_utils.count_characters(sample_text, include_spaces=False)
    print(f"Character count (with spaces): {char_count_spaces}")
    print(f"Character count (no spaces): {char_count_no_spaces}")
    
    simple_wc = word_counter.count_words_simple(sample_text)
    print(f"Simple word count: {simple_wc}")
    
    advanced_wc = word_counter.count_words_advanced(sample_text)
    print(f"Advanced word counts: {advanced_wc}")
    print("-" * 30)

if __name__ == "__main__":
    text1 = "Hello, World! This is a test."
    text2 = "The quick brown fox and the lazy dog. The."
    text3 = "Python is fun, Python is powerful."
    
    demonstrate_analyzer(text1)
    demonstrate_analyzer(text2) # This will show the 'the' count being off by one
    demonstrate_analyzer(text3)