from pathlib import Path

from app.services.claims import extract_claims


def test_claim_extraction_from_fixture():
    fixture = Path(__file__).parent / "fixtures" / "sample_article.txt"
    text = fixture.read_text(encoding="utf-8")
    claims = extract_claims(text)
    assert len(claims) >= 1
    # At least one claim must contain a verifiable number (% or $)
    assert any(any(n.get("unit") in {"%", "$"} for n in c["numbers"]) for c in claims)


def test_claim_has_category_and_score():
    fixture = Path(__file__).parent / "fixtures" / "sample_article.txt"
    text = fixture.read_text(encoding="utf-8")
    claims = extract_claims(text)
    for c in claims:
        assert "sensational_score" in c
        assert "category" in c
        assert c["sensational_score"] >= 1.0
        assert isinstance(c["category"], str)


def test_bare_years_not_captured_as_numbers():
    """Bare years like 2021 / 2024 without comparative context should be dropped."""
    text = (
        "In 2021, Apple tested its own CSAM-detection features. "
        "The company reported revenue of $25 billion for the quarter."
    )
    claims = extract_claims(text)
    for c in claims:
        for n in c["numbers"]:
            # No bare year should appear as a claim number
            if n.get("unit") is None:
                assert not (1900 <= n["value"] <= 2100), (
                    f"Bare year {n['value']} should not be a claim number"
                )


def test_historical_recap_penalised():
    """Sentences that just recap old events should score lower."""
    sensational = "Tesla shares surged 25% on record-breaking quarterly revenue of $25 billion."
    recap = "Back in 2009, the company was valued at $1 billion before the crisis."

    sensational_claims = extract_claims(sensational)
    recap_claims = extract_claims(recap)

    if sensational_claims and recap_claims:
        assert sensational_claims[0]["sensational_score"] > recap_claims[0]["sensational_score"]
