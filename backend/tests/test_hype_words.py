from app.services.hype import score_hype


def test_hype_score_detects_phrases_and_words():
    text = "The stock skyrockets after it SMASHES expectations! This is jaw-dropping."
    score, top, ratio = score_hype(text)
    assert score > 0
    # Ensure at least one known phrase/word was counted.
    assert sum(c for _, c in top) >= 1
    assert ratio > 0


def test_hype_score_low_for_neutral_text():
    text = "The company reported revenue of $10 billion and guidance for next quarter."
    score, top, ratio = score_hype(text)
    assert score >= 0
    assert ratio >= 0
