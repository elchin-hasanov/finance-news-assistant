from app.services.reliability import compute_reliability_score


def test_reliable_article_scores_high():
    text = (
        "According to the SEC filing, Apple Inc. reported quarterly revenue of $94.8 billion, "
        "down 5% compared to the year-ago quarter. Tim Cook, CEO of Apple, stated that the "
        "results reflect continued investment in innovation. However, some analysts noted "
        "concern about declining iPhone sales in China. On the other hand, the services "
        "segment grew 11% year over year to a record $23.1 billion, according to the "
        "company's earnings release. Goldman Sachs analyst Rod Hall maintained a neutral "
        "rating. It should be noted that macroeconomic uncertainty and currency headwinds "
        "remain risk factors."
    )
    result = compute_reliability_score(text)
    assert result["reliability_score"] >= 60
    assert result["reliability_label"] in {"Highly Reliable", "Generally Reliable"}


def test_clickbait_article_scores_low():
    text = (
        "SHOCKING! Tesla stock is about to EXPLODE! Sources say the stock could skyrocket "
        "200% by next month! This is a once in a lifetime opportunity. BUY NOW before "
        "it is too late! Experts believe this is the biggest opportunity ever! Massive "
        "gains are coming! Do not miss this incredible moonshot! Already surged 50%!!!"
    )
    result = compute_reliability_score(text)
    assert result["reliability_score"] < 30
    assert "Unreliable" in result["reliability_label"]


def test_score_within_bounds():
    for text in ["Short.", "A" * 5000, ""]:
        result = compute_reliability_score(text)
        assert 0 <= result["reliability_score"] <= 100
        assert isinstance(result["reliability_label"], str)
        assert isinstance(result["signals"], dict)
