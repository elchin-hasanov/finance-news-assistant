from app.services.hype import score_hype


def test_hype_scoring_counts_words_and_bonus():
    text = "TSLA surges and soars!!! UNBELIEVABLE move"
    score, top, ratio = score_hype(text)
    assert ratio > 0
    assert score >= 1
    assert any(w == "surges" for w, _ in top)
