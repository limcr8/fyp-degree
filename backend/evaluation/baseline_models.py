"""
Trains and evaluates baseline models (Naive Bayes, Logistic Regression) on the
same test data for comparison against RoBERTa. Includes 5-fold cross-validation.
Does NOT touch the deployed RoBERTa model.
"""
import json
import time
import os
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)
from sklearn.model_selection import StratifiedKFold, cross_val_score


def load_data(csv_path: str):
    df = pd.read_csv(csv_path)
    texts = df["text"].astype(str).tolist()
    raw_labels = df["label"].str.strip().str.upper().tolist()
    labels = [1 if l in ("FAKE", "1") else 0 for l in raw_labels]
    return texts, np.array(labels), df


def evaluate_model(name, model, X_train, X_test, y_train, y_test):
    start = time.perf_counter()
    model.fit(X_train, y_train)
    train_time = time.perf_counter() - start

    start = time.perf_counter()
    predictions = model.predict(X_test)
    inference_time = (time.perf_counter() - start) / len(y_test) * 1000

    metrics = {
        "model": name,
        "accuracy": round(accuracy_score(y_test, predictions), 4),
        "precision_macro": round(precision_score(y_test, predictions, average="macro"), 4),
        "recall_macro": round(recall_score(y_test, predictions, average="macro"), 4),
        "f1_macro": round(f1_score(y_test, predictions, average="macro"), 4),
        "train_time_s": round(train_time, 2),
        "inference_ms": round(inference_time, 2),
    }
    cm = confusion_matrix(y_test, predictions)
    print(f"\n{'=' * 50}")
    print(f"{name}")
    print(f"{'=' * 50}")
    print(json.dumps(metrics, indent=2))
    print(f"\nConfusion Matrix (TP/TN/FP/FN):")
    print(f"  TP={cm[1][1]} TN={cm[0][0]} FP={cm[0][1]} FN={cm[1][0]}")
    print(f"\n{classification_report(y_test, predictions, target_names=['REAL', 'FAKE'])}")
    return metrics, model


def run_cross_validation(model, X, y, name):
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=skf, scoring="f1_macro")
    print(f"\n5-Fold CV for {name}:")
    print(f"  F1 scores: {[round(s, 4) for s in scores]}")
    print(f"  Mean F1: {scores.mean():.4f} +/- {scores.std():.4f}")
    return {"mean_f1": round(float(scores.mean()), 4), "std_f1": round(float(scores.std()), 4)}


def main():
    csv_path = "evaluation/crypto_finance_testset.csv"
    print("Loading data...")
    texts, labels, df = load_data(csv_path)
    print(f"Total samples: {len(texts)}")

    print("\nVectorizing text with TF-IDF...")
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english", ngram_range=(1, 2))
    X = vectorizer.fit_transform(texts)
    y = labels

    split = int(len(texts) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    print(f"Train: {X_train.shape[0]} | Test: {X_test.shape[0]}")

    models = [
        ("Naive Bayes", MultinomialNB()),
        ("Logistic Regression", LogisticRegression(max_iter=1000, random_state=42)),
    ]

    all_results = []
    cv_results = {}

    for name, model in models:
        metrics, trained_model = evaluate_model(name, model, X_train, X_test, y_train, y_test)
        all_results.append(metrics)
        cv = run_cross_validation(trained_model, X, y, name)
        cv_results[name] = cv

    print("\n" + "=" * 60)
    print("SUMMARY: Baseline vs RoBERTa")
    print("=" * 60)

    roberta_path = "evaluation/roberta_results.json"
    if os.path.exists(roberta_path):
        with open(roberta_path) as f:
            roberta = json.load(f)
        rm = roberta["metrics"]
        print(f"\n{'Model':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Time(ms)':>10}")
        print("-" * 75)
        for r in all_results:
            print(f"{r['model']:<25} {r['accuracy']:>10.4f} {r['precision_macro']:>10.4f} {r['recall_macro']:>10.4f} {r['f1_macro']:>10.4f} {r['inference_ms']:>10.2f}")
        print(f"{'RoBERTa':<25} {rm['accuracy']:>10.4f} {rm['precision_macro']:>10.4f} {rm['recall_macro']:>10.4f} {rm['f1_macro']:>10.4f} {rm['avg_inference_ms']:>10.2f}")
    else:
        print("\n(Run evaluate_roberta.py first to include RoBERTa in comparison)")

    output = {"baselines": all_results, "cross_validation": cv_results}
    with open("evaluation/baseline_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: evaluation/baseline_results.json")


if __name__ == "__main__":
    main()
