import re

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd",
    "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that",
    "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's",
    "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom",
    "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves"
}

def _normalize_text(text: str) -> list:
    """Lowercase, strip punctuation, tokenize and remove stopwords."""
    if not text:
        return []
    # Lowercase
    text = text.lower()
    # Remove punctuation using regex, leaving alphanumeric and spaces
    text = re.sub(r'[^\w\s]', '', text)
    # Tokenize
    tokens = text.split()
    # Remove stopwords
    filtered_tokens = [t for t in tokens if t not in STOPWORDS]
    return filtered_tokens

def _get_trigrams(tokens: list) -> set:
    """Generate word trigrams from tokens."""
    trigrams = set()
    for i in range(len(tokens) - 2):
        trigrams.add(f"{tokens[i]}_{tokens[i+1]}_{tokens[i+2]}")
    return trigrams

def _jaccard_similarity(set1: set, set2: set) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0

def _get_opening_phrase(text: str, word_count: int = 6) -> str:
    """Get the first N words of a text, normalized."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    return " ".join(words[:word_count])

def _get_distinctive_words(tokens: list, min_length: int = 6) -> set:
    """Find words longer than min_length."""
    return {t for t in tokens if len(t) >= min_length}

def isRoastTooSimilar(candidate: dict, recentRoasts: list, options: dict = None) -> dict:
    """
    Check if a candidate roast is too similar to recent roasts.
    """
    if options is None:
        options = {}
        
    max_title_sim = options.get("maxTitleSimilarity", 0.9)
    max_msg_sim = options.get("maxMessageSimilarity", 0.6)
    max_trigram_sim = options.get("maxTrigramSimilarity", 0.3)
    lookback = options.get("lookbackCount", 5)
    
    cand_title = candidate.get("title", "")
    cand_msg = candidate.get("message", "")
    
    if not cand_title and not cand_msg:
        return {"tooSimilar": False, "reason": None, "similarityScore": 0.0}
        
    cand_title_norm = cand_title.strip().lower()
    cand_msg_norm = cand_msg.strip().lower()
    
    cand_tokens = _normalize_text(cand_msg)
    cand_set = set(cand_tokens)
    cand_trigrams = _get_trigrams(cand_tokens)
    cand_opening = _get_opening_phrase(cand_msg)
    cand_distinctive = _get_distinctive_words(cand_tokens)
    
    roasts_to_check = recentRoasts[:lookback]
    
    for hist in roasts_to_check:
        hist_title = hist.get("title", "")
        hist_msg = hist.get("message", "")
        
        hist_title_norm = hist_title.strip().lower()
        hist_msg_norm = hist_msg.strip().lower()
        
        # 1. Exact normalized matches
        if cand_title_norm and hist_title_norm and cand_title_norm == hist_title_norm:
            return {"tooSimilar": True, "reason": "Exact title match", "similarityScore": 1.0, "matchedRecentRoast": hist}
            
        if cand_msg_norm and hist_msg_norm and cand_msg_norm == hist_msg_norm:
            return {"tooSimilar": True, "reason": "Exact message match", "similarityScore": 1.0, "matchedRecentRoast": hist}
            
        # 2. Opening phrase match
        hist_opening = _get_opening_phrase(hist_msg)
        if cand_opening and hist_opening and cand_opening == hist_opening:
            return {"tooSimilar": True, "reason": "Same opening phrase", "similarityScore": 1.0, "matchedRecentRoast": hist}
            
        # 3. Token overlap (Jaccard)
        hist_tokens = _normalize_text(hist_msg)
        hist_set = set(hist_tokens)
        
        jaccard_score = _jaccard_similarity(cand_set, hist_set)
        if jaccard_score > max_msg_sim:
            return {"tooSimilar": True, "reason": f"High token overlap ({jaccard_score:.2f})", "similarityScore": jaccard_score, "matchedRecentRoast": hist}
            
        # 4. Trigram overlap
        hist_trigrams = _get_trigrams(hist_tokens)
        trigram_score = _jaccard_similarity(cand_trigrams, hist_trigrams)
        if trigram_score > max_trigram_sim:
            return {"tooSimilar": True, "reason": f"High trigram overlap ({trigram_score:.2f})", "similarityScore": trigram_score, "matchedRecentRoast": hist}
            
        # 5. Repeated distinctive phrases/words
        hist_distinctive = _get_distinctive_words(hist_tokens)
        if cand_distinctive and hist_distinctive:
            distinctive_overlap = _jaccard_similarity(cand_distinctive, hist_distinctive)
            if distinctive_overlap > 0.5: # 50% overlap in distinctive words
                return {"tooSimilar": True, "reason": "Repeated distinctive words", "similarityScore": distinctive_overlap, "matchedRecentRoast": hist}
                
    return {"tooSimilar": False, "reason": None, "similarityScore": 0.0}
