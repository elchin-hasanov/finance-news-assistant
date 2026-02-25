"""Quick test of reliability scoring on two extreme examples."""
from app.services.reliability import compute_reliability_score

balanced = (
    "According to the SEC filing, Apple Inc. reported quarterly revenue of $94.8 billion, "
    "down 5% compared to the year-ago quarter. Tim Cook, CEO of Apple, stated that the "
    "results reflect continued investment in innovation. However, some analysts noted "
    "concern about declining iPhone sales in China. On the other hand, the services "
    "segment grew 11% year over year to a record $23.1 billion, according to the "
    "company's earnings release. Goldman Sachs analyst Rod Hall maintained a neutral "
    "rating, while Morgan Stanley's Erik Woodring raised his price target. It should "
    "be noted that macroeconomic uncertainty and currency headwinds remain risk factors. "
    "Revenue was $94.8 billion compared to consensus estimates of $95.4 billion."
)
result = compute_reliability_score(balanced)
print(f"Balanced article: {result['reliability_score']} — {result['reliability_label']}")
for k, v in result["signals"].items():
    print(f"  {k}: {v}")

hyped = (
    "SHOCKING! Tesla stock is about to EXPLODE! Sources say the stock could skyrocket "
    "200% by next month! This is a once in a lifetime opportunity. BUY NOW before "
    "it is too late! Experts believe this is the biggest opportunity ever! Massive "
    "gains are coming! Do not miss out on this incredible moonshot! The stock has "
    "already surged 50% and could triple from here!!!"
)
result2 = compute_reliability_score(hyped)
print(f"\nHyped article: {result2['reliability_score']} — {result2['reliability_label']}")
for k, v in result2["signals"].items():
    print(f"  {k}: {v}")
