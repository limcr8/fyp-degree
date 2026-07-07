"""
Downloads a REAL human-written fake news dataset from HuggingFace.
Filters for financial/crypto content to match the project's domain.

This replaces synthetic templates with actual news articles.
"""
import csv
import os
import re
import random

random.seed(42)

# Keywords to filter financial/crypto content
DOMAIN_KEYWORDS = [
    # Crypto
    "bitcoin", "ethereum", "crypto", "blockchain", "token", "defi", "nft",
    "coinbase", "binance", "altcoin", "mining", "wallet", "satoshi",
    "solana", "cardano", "xrp", "dogecoin", "polygon", "avalanche",
    # Finance
    "stock", "market", "trading", "investor", "investment", "profit",
    "revenue", "earnings", "fed", "rate", "interest", "inflation",
    "treasury", "bond", "dollar", "currency", "bank", "economic",
    "oil", "gold", "commodity", "fund", "ipo", "acquisition",
    "merger", "shareholder", "dividend", "nasdaq", "dow", "s&p",
    "securities", "exchange", "financial", "fiscal", "monetary",
    "sec ", "regulation", "sanction", "trade", "tariff", "gdp",
]


def download_dataset():
    """Downloads the GonzaloA/fake_news dataset from HuggingFace."""
    print("Downloading real fake news dataset from HuggingFace...")
    print("Dataset: GonzaloA/fake_news (48,898 real human-written articles)")

    try:
        from datasets import load_dataset
    except ImportError:
        print("Installing datasets library...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets", "-q"])
        from datasets import load_dataset

    # This dataset has columns: text, label (0=real, 1=fake)
    ds = load_dataset("GonzaloA/fake_news", split="train")
    print(f"Downloaded {len(ds)} articles total")

    rows = []
    domain_filtered = 0
    skipped_short = 0

    for item in ds:
        text = (item.get("text") or "").strip()
        label_int = item.get("label", -1)
        title = (item.get("title") or "").strip()

        # Combine title + text for richer content
        full_text = f"{title}. {text}" if title else text

        # Skip very short texts (not useful for evaluation)
        if len(full_text) < 100:
            skipped_short += 1
            continue

        # Check if this article is financial/crypto related
        text_lower = full_text.lower()
        is_domain = any(kw in text_lower for kw in DOMAIN_KEYWORDS)

        if not is_domain:
            continue

        domain_filtered += 1

        label = "fake" if label_int == 1 else "real"
        rows.append({
            "text": full_text[:2000],  # Cap at 2000 chars for memory
            "label": label,
            "category": "finance",
            "source": "GonzaloA/fake_news",
            "language": "en",
        })

    print(f"Filtered to {domain_filtered} financial/crypto articles")
    print(f"Skipped {skipped_short} articles that were too short")

    if len(rows) < 200:
        print("\nWARNING: Few domain-specific articles found.")
        print("Including a sample of general news articles for sufficient sample size.")

        # Add some general articles to reach minimum viable size
        general_added = 0
        for item in ds:
            if general_added >= 300:
                break
            text = (item.get("text") or "").strip()
            label_int = item.get("label", -1)
            title = (item.get("title") or "").strip()
            full_text = f"{title}. {text}" if title else text

            if len(full_text) < 100:
                continue

            # Check if already added (domain-filtered)
            if any(kw in full_text.lower() for kw in DOMAIN_KEYWORDS):
                continue

            label = "fake" if label_int == 1 else "real"
            rows.append({
                "text": full_text[:2000],
                "label": label,
                "category": "general",
                "source": "GonzaloA/fake_news",
                "language": "en",
            })
            general_added += 1

        print(f"Added {general_added} general articles")

    # Balance the dataset (equal real/fake)
    real_rows = [r for r in rows if r["label"] == "real"]
    fake_rows = [r for r in rows if r["label"] == "fake"]
    min_count = min(len(real_rows), len(fake_rows))

    # Cap at 500 total for reasonable evaluation time
    target_per_class = min(min_count, 250)

    real_sample = random.sample(real_rows, target_per_class)
    fake_sample = random.sample(fake_rows, target_per_class)

    final_rows = real_sample + fake_sample
    random.shuffle(final_rows)

    return final_rows


def main():
    rows = download_dataset()

    os.makedirs("evaluation", exist_ok=True)
    output_path = os.path.join("evaluation", "crypto_finance_testset.csv")

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "category", "source", "language"])
        writer.writeheader()
        writer.writerows(rows)

    real_n = sum(1 for r in rows if r["label"] == "real")
    fake_n = sum(1 for r in rows if r["label"] == "fake")
    finance_n = sum(1 for r in rows if r["category"] == "finance")
    general_n = sum(1 for r in rows if r["category"] == "general")

    print(f"\nDataset saved: {output_path}")
    print(f"Total rows: {len(rows)}")
    print(f"Real: {real_n} | Fake: {fake_n}")
    print(f"Financial/Crypto: {finance_n} | General: {general_n}")

    print(f"\nSample REAL row:")
    real_rows = [r for r in rows if r["label"] == "real"]
    if real_rows:
        print(f"  {real_rows[0]['text'][:150]}...")

    print(f"\nSample FAKE row:")
    fake_rows = [r for r in rows if r["label"] == "fake"]
    if fake_rows:
        print(f"  {fake_rows[0]['text'][:150]}...")


if __name__ == "__main__":
    main()
