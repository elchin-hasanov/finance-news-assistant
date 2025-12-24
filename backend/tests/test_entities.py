from app.services.entities import extract_companies, extract_tickers, infer_company_tickers, infer_ticker_aliases


def test_extract_tickers_exchange_tag_and_dollar():
    text = "Apple (NASDAQ: AAPL) is up. $TSLA is down."
    assert extract_tickers(text) == ["AAPL", "TSLA"]


def test_extract_tickers_avoids_stop_words():
    text = "The CEO said EPS beat the FED forecast."
    assert extract_tickers(text) == []


def test_extract_tickers_bare_only_with_context():
    assert extract_tickers("AAPL is great") == []
    assert extract_tickers("The stock AAPL rose after earnings") == ["AAPL"]


def test_infer_alias_bp():
    text = "Britain's BP said it will sell assets."
    aliases = infer_ticker_aliases(text)
    assert aliases.get("BP") == "BP"


def test_infer_company_tickers_sp500_dataset():
    companies = ["Apple Inc.", "Microsoft Corporation", "Berkshire Hathaway"]
    out = infer_company_tickers(companies, ticker_aliases={})
    assert out["Apple Inc."] == "AAPL"
    assert out["Microsoft Corporation"] == "MSFT"
    # Ensure dot tickers normalize to dash for downstream yfinance usage.
    assert out["Berkshire Hathaway"] == "BRK-B"


def test_extract_companies_market_wrap_list_formatting():
    text = (
        "Major U.S. indexes climbed for a fourth straight session on Tuesday, led by tech names including\n"
        "Google parent Alphabet\n"
        ", Nvidia\n"
        ", Broadcom\n"
        "and Amazon.\n"
    )
    companies = extract_companies(text, tickers=[])

    # We don't enforce exact strings (suffixes/parenthetical class names vary),
    # but these key names should be present.
    joined = " | ".join(companies).lower()
    assert "alphabet" in joined
    assert "nvidia" in joined
    assert "broadcom" in joined
    assert "amazon" in joined
