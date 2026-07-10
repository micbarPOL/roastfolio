import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from similarity_detector import isRoastTooSimilar, _normalize_text, _get_trigrams, _get_opening_phrase

def test_normalization():
    text = "Wow! The market is up 5.0%, but you are down... 2.5%?? That's insane."
    tokens = _normalize_text(text)
    # Stopwords like "the", "is", "but", "you", "are", "that's" should be removed
    assert "market" in tokens
    assert "insane" in tokens
    assert "the" not in tokens
    assert "is" not in tokens

def test_opening_phrase():
    text = "In a stunning twist your portfolio reflects your personality."
    opening = _get_opening_phrase(text)
    assert opening == "in a stunning twist your portfolio"

def test_exact_match():
    cand = {"title": "Title A", "message": "Exact message match."}
    hist = [{"title": "Title B", "message": "Exact message match."}]
    res = isRoastTooSimilar(cand, hist)
    assert res["tooSimilar"] is True
    assert res["reason"] == "Exact message match"

def test_same_opening():
    cand = {"title": "A", "message": "In a stunning twist, you really lost everything today."}
    hist = [{"title": "B", "message": "In a stunning twist, you really gained everything yesterday."}]
    res = isRoastTooSimilar(cand, hist)
    assert res["tooSimilar"] is True
    assert res["reason"] == "Same opening phrase"

def test_high_overlap():
    cand = {"title": "A", "message": "The market went up and you lost all your money."}
    hist = [{"title": "B", "message": "The market went up, unfortunately you lost all money."}]
    res = isRoastTooSimilar(cand, hist)
    assert res["tooSimilar"] is True
    assert "High token overlap" in res["reason"] or "High trigram overlap" in res["reason"]

def test_not_similar():
    cand = {"title": "Fresh Title", "message": "You made a smart deposit today and built up your savings."}
    hist = [{"title": "Old Title", "message": "The market fell apart and everything is ruined."}]
    res = isRoastTooSimilar(cand, hist)
    assert res["tooSimilar"] is False

def test_empty_history():
    cand = {"title": "A", "message": "B"}
    res = isRoastTooSimilar(cand, [])
    assert res["tooSimilar"] is False
