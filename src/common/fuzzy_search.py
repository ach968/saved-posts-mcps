"""Fuzzy search utilities for matching queries against text content."""

from rapidfuzz import fuzz


def fuzzy_word_match(word: str, text: str, threshold: int) -> bool:
    """
    Check if a word appears in text with fuzzy tolerance.

    Args:
        word: The word to search for
        text: The text to search in
        threshold: Max edit distance (0 disables fuzzy matching)

    Returns:
        True if word matches any word in text within threshold
    """
    text_words = text.lower().split()
    word_lower = word.lower()

    for text_word in text_words:
        # Exact match
        if word_lower == text_word:
            return True
        # Fuzzy match for words 4+ chars only (avoid false positives on short words)
        if threshold > 0 and len(word_lower) > 3:
            # Convert threshold to similarity ratio (threshold=2 -> 80% similarity)
            min_ratio = 100 - (threshold * 10)
            if fuzz.ratio(word_lower, text_word) >= min_ratio:
                return True
    return False


def fuzzy_search(
    text: str,
    queries: list[str],
    match_all: bool = True,
    fuzzy_threshold: int = 2,
) -> bool:
    """
    Check if text matches the search queries with fuzzy tolerance.

    Args:
        text: The text to search in
        queries: List of search terms
        match_all: If True, all queries must match (AND). If False, any query matches (OR).
        fuzzy_threshold: Max edit distance for fuzzy matching (0 disables fuzzy)

    Returns:
        True if text matches according to match_all logic
    """
    if not queries:
        return True

    matches = [fuzzy_word_match(q, text, fuzzy_threshold) for q in queries]

    if match_all:
        return all(matches)
    return any(matches)
