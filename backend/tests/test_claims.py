from pathlib import Path

from app.services.claims import extract_claims


def test_claim_extraction_from_fixture():
    fixture = Path(__file__).parent / "fixtures" / "sample_article.txt"
    text = fixture.read_text(encoding="utf-8")
    claims = extract_claims(text)
    assert len(claims) >= 2
    assert any(any(n.get("unit") in {"%", "$"} for n in c["numbers"]) for c in claims)
