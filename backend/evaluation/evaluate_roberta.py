"""
Evaluates the deployed RoBERTa model on the test dataset.
READ-ONLY: Does NOT modify the model or the live system in any way.
"""
import argparse
import json
import os
import time

import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
from transformers import AutoTokenizer, AutoModelForSequenceClassification


def load_test_data(csv_path: str):
    df = pd.read_csv(csv_path)
    texts = df["text"].astype(str).tolist()
    raw_labels = df["label"].str.strip().str.upper().tolist()
    labels = [1 if l in ("FAKE", "1") else 0 for l in raw_labels]
    return texts, labels, df


def evaluate_roberta(model_path: str, texts, true_labels):
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    predictions = []
    confidences = []
    total_time = 0.0

    print(f"Running inference on {len(texts)} samples (device: {device})...")

    with torch.no_grad():
        for i, text in enumerate(texts):
            if i % 100 == 0:
                print(f"  Progress: {i}/{len(texts)}")

            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}

            start = time.perf_counter()
            outputs = model(**inputs)
            elapsed = time.perf_counter() - start
            total_time += elapsed

            probs = torch.softmax(outputs.logits, dim=-1)
            conf, pred = torch.max(probs, dim=-1)
            predictions.append(int(pred.item()))
            confidences.append(round(float(conf.item()), 4))

    avg_inference_ms = (total_time / len(texts)) * 1000
    return predictions, confidences, avg_inference_ms


def compute_metrics(true_labels, predictions):
    cm = confusion_matrix(true_labels, predictions)
    tn, fp, fn, tp = cm.ravel()

    metrics = {
        "accuracy": round(accuracy_score(true_labels, predictions), 4),
        "precision_macro": round(precision_score(true_labels, predictions, average="macro"), 4),
        "recall_macro": round(recall_score(true_labels, predictions, average="macro"), 4),
        "f1_macro": round(f1_score(true_labels, predictions, average="macro"), 4),
        "precision_fake": round(precision_score(true_labels, predictions, pos_label=1), 4),
        "recall_fake": round(recall_score(true_labels, predictions, pos_label=1), 4),
        "f1_fake": round(f1_score(true_labels, predictions, pos_label=1), 4),
        "precision_real": round(precision_score(true_labels, predictions, pos_label=0), 4),
        "recall_real": round(recall_score(true_labels, predictions, pos_label=0), 4),
        "f1_real": round(f1_score(true_labels, predictions, pos_label=0), 4),
        "confusion_matrix": {
            "true_positive": int(tp),
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
        },
    }
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate RoBERTa fake news model.")
    parser.add_argument("--model", default="checkpoints/roberta-fake-news", help="Path to model checkpoint")
    parser.add_argument("--test-data", default="evaluation/crypto_finance_testset.csv", help="Path to test CSV")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"ERROR: Model not found at {args.model}")
        return
    if not os.path.exists(args.test_data):
        print(f"ERROR: Test data not found at {args.test_data}")
        print("Run generate_dataset.py first.")
        return

    print("=" * 60)
    print("RoBERTa Model Evaluation")
    print("=" * 60)

    texts, true_labels, df = load_test_data(args.test_data)
    print(f"Loaded {len(texts)} test samples")
    print(f"  Real: {true_labels.count(0)} | Fake: {true_labels.count(1)}")

    predictions, confidences, avg_time = evaluate_roberta(args.model, texts, true_labels)
    metrics = compute_metrics(true_labels, predictions)
    metrics["avg_inference_ms"] = round(avg_time, 2)
    metrics["total_samples"] = len(texts)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(json.dumps(metrics, indent=2))

    print("\n" + "=" * 60)
    print("CLASSIFICATION REPORT")
    print("=" * 60)
    print(classification_report(true_labels, predictions, target_names=["REAL", "FAKE"]))

    print(f"\nAvg Inference Time: {avg_time:.2f} ms/sample")

    report = {
        "model": args.model,
        "test_data": args.test_data,
        "metrics": metrics,
        "full_report": classification_report(true_labels, predictions, target_names=["REAL", "FAKE"], output_dict=True),
        "errors": [
            {"text": texts[i][:120], "actual": "FAKE" if true_labels[i] == 1 else "REAL",
             "predicted": "FAKE" if predictions[i] == 1 else "REAL",
             "confidence": confidences[i]}
            for i in range(len(texts)) if predictions[i] != true_labels[i]
        ][:20],
    }

    output_path = "evaluation/roberta_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nFull report saved to: {output_path}")
    print(f"Misclassified samples saved: {len(report['errors'])}")


if __name__ == "__main__":
    main()
