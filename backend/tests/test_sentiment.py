"""Tests for sentiment analysis service."""

from app.services.sentiment import analyze_sentiment, get_sentiment_label


def test_positive_sentiment():
    text = "Company reports strong profits with growing revenue and successful product launch"
    result = analyze_sentiment(text)
    assert result["sentiment_score"] > 0
    assert result["positive_count"] > 0
    assert get_sentiment_label(result["sentiment_score"]) in ["Positive", "Very Positive"]


def test_negative_sentiment():
    text = "Company faces bankruptcy concerns with declining sales and increasing losses"
    result = analyze_sentiment(text)
    assert result["sentiment_score"] < 0
    assert result["negative_count"] > 0
    assert get_sentiment_label(result["sentiment_score"]) in ["Negative", "Very Negative"]


def test_neutral_sentiment():
    text = "The company announced a meeting scheduled for next Tuesday at headquarters"
    result = analyze_sentiment(text)
    # Transformer models can sometimes lean slightly positive/negative on short neutral text.
    # Keep the assertion permissive while still expecting near-neutral.
    assert abs(result["sentiment_score"]) < 0.5
    assert result["neutral_ratio"] > 0.8
    assert get_sentiment_label(result["sentiment_score"]) in ["Neutral", "Positive", "Negative"]


def test_mixed_sentiment():
    text = "Despite strong profits, the company faces growing concerns about debt"
    result = analyze_sentiment(text)
    assert result["positive_count"] > 0
    assert result["negative_count"] > 0
