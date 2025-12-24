from __future__ import annotations

from app.services.fetching import extract_article_text


def test_extract_article_text_prefers_article_paragraphs_and_ignores_nav_footer() -> None:
    html = """
    <html>
      <head>
        <title>Example</title>
        <meta property="article:published_time" content="2025-12-24T12:00:00Z" />
      </head>
      <body>
        <nav>
          Markets Europe Markets China Markets Asia Markets World Markets
          SIGN IN Create free account
        </nav>
        <article>
          <h1>Headline</h1>
          <p>This is the first paragraph of the article with meaningful content that should be extracted.</p>
          <p>This is the second paragraph with additional context and numbers like 0.1% and S&P 500.</p>
        </article>
        <footer>
          Subscribe PRO Privacy Terms
        </footer>
      </body>
    </html>
    """

    text, title, pub = extract_article_text(html)
    assert title == "Example"
    assert pub == "2025-12-24"

    assert "first paragraph" in text
    assert "second paragraph" in text

    # Nav/footer boilerplate should not dominate the extracted body.
    assert "Create free account" not in text
    assert "Markets Europe Markets" not in text


def test_extract_article_text_uses_jsonld_articleBody_when_present() -> None:
    html = """
    <html>
      <head>
        <title>JSONLD</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          "headline": "Hello",
          "articleBody": "This is the real body text. It should be extracted instead of the page chrome."
        }
        </script>
      </head>
      <body>
        <div>Menu Markets Sign in</div>
        <main>
          <div>Not the body</div>
        </main>
      </body>
    </html>
    """

    text, title, _ = extract_article_text(html)
    assert title == "JSONLD"
    assert "real body text" in text
    assert "Menu Markets" not in text
