"""
Downloads a larger dataset for TRAINING (not the 500-row test set).
Produces: evaluation/training_dataset.csv (2000+ rows)
Then fine-tunes RoBERTa using the existing train_roberta.py pipeline.
Saves to: checkpoints/roberta-fake-news-v2/ (NEW directory, does NOT touch current model)
"""
import csv
import os
import random
import subprocess
import sys

random.seed(42)

DOMAIN_KEYWORDS = [
    "bitcoin", "ethereum", "crypto", "blockchain", "token", "defi", "nft",
    "coinbase", "binance", "altcoin", "mining", "wallet", "satoshi",
    "stock", "market", "trading", "investor", "investment", "profit",
    "revenue", "earnings", "fed", "rate", "interest", "inflation",
    "treasury", "bond", "dollar", "currency", "bank", "economic",
    "oil", "gold", "commodity", "fund", "ipo", "acquisition",
    "merger", "shareholder", "dividend", "nasdaq", "financial",
    "sec ", "regulation", "trade", "tariff", "gdp", "company",
    "business", "corporate", "industry", "technology", "government",
    "president", "senate", "congress", "election", "policy", "law",
]


def download_training_data():
    """Downloads a larger dataset for training."""
    print("=" * 60)
    print("Step 1: Downloading training dataset from HuggingFace")
    print("=" * 60)

    from datasets import load_dataset

    ds = load_dataset("GonzaloA/fake_news", split="train")
    print(f"Downloaded {len(ds)} articles total from HuggingFace")

    all_rows = []
    for item in ds:
        text = (item.get("text") or "").strip()
        label_int = item.get("label", -1)
        title = (item.get("title") or "").strip()
        full_text = f"{title}. {text}" if title else text

        if len(full_text) < 80:
            continue

        label = "fake" if label_int == 1 else "real"
        all_rows.append({
            "text": full_text[:2000],
            "label": label,
            "category": "general",
            "source": "GonzaloA/fake_news",
            "language": "en",
        })

    # Balance: take up to 1500 per class = 3000 total
    real_rows = [r for r in all_rows if r["label"] == "real"]
    fake_rows = [r for r in all_rows if r["label"] == "fake"]
    max_per_class = min(len(real_rows), len(fake_rows), 1500)

    real_sample = random.sample(real_rows, max_per_class)
    fake_sample = random.sample(fake_rows, max_per_class)
    final_rows = real_sample + fake_sample
    random.shuffle(final_rows)

    output_path = os.path.join("evaluation", "training_dataset.csv")
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "category", "source", "language"])
        writer.writeheader()
        writer.writerows(final_rows)

    print(f"Training dataset saved: {output_path}")
    print(f"Total rows: {len(final_rows)} (Real: {max_per_class}, Fake: {max_per_class})")
    return output_path


def fine_tune(dataset_path: str):
    """Runs the existing train_roberta.py to fine-tune the model."""
    print("\n" + "=" * 60)
    print("Step 2: Fine-tuning RoBERTa (this may take 10-30 minutes)")
    print("Saving to: checkpoints/roberta-fake-news-v2/")
    print("Your current model at checkpoints/roberta-fake-news/ is UNTOUCHED")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "training.train_roberta",
        "--dataset", dataset_path,
        "--output-dir", "checkpoints/roberta-fake-news-v2",
        "--base-model", "roberta-base",
        "--epochs", "3",
        "--batch-size", "8",
        "--learning-rate", "2e-5",
        "--min-examples", "4",
        "--min-examples-per-label", "2",
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=os.getcwd())

    if result.returncode != 0:
        print("ERROR: Training failed. Check the output above.")
        sys.exit(1)

    print("\nTraining complete! New model saved to: checkpoints/roberta-fake-news-v2/")


def main():
    dataset_path = download_training_data()
    fine_tune(dataset_path)

    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Evaluate the NEW model:")
    print("   python evaluation/evaluate_roberta.py --model checkpoints/roberta-fake-news-v2")
    print()
    print("2. Run baselines for comparison:")
    print("   python evaluation/baseline_models.py")
    print()
    print("3. If happy with results, deploy the new model by updating .env:")
    print("   ROBERTA_MODEL_NAME_OR_PATH=./checkpoints/roberta-fake-news-v2")
    print()
    print("4. If NOT happy, your old model is still safe at:")
    print("   checkpoints/roberta-fake-news/")


if __name__ == "__main__":
    main()
