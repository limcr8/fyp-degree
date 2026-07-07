import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LABEL_ALIASES = {
    "real": "REAL",
    "true": "REAL",
    "credible": "REAL",
    "reliable": "REAL",
    "0": "REAL",
    "fake": "FAKE",
    "false": "FAKE",
    "misinformation": "FAKE",
    "unreliable": "FAKE",
    "1": "FAKE",
}


@dataclass(frozen=True)
class TrainingConfig:
    """
    RoBERTa fine-tuning configuration.

    Attributes:
        dataset_path (Path): CSV dataset path.
        output_dir (Path): Directory where the checkpoint is saved.
        base_model (str): Hugging Face base model or local path.
        text_column (str): CSV column containing article text.
        label_column (str): CSV column containing labels.
        epochs (float): Number of training epochs.
        batch_size (int): Per-device training/evaluation batch size.
        learning_rate (float): Optimizer learning rate.
        eval_ratio (float): Validation split ratio.
        seed (int): Random seed.
        min_examples (int): Minimum valid rows required for normal training.
        min_examples_per_label (int): Minimum valid rows required for each label.
        use_class_weights (bool): Whether to weight loss by class frequency.
    """

    dataset_path: Path
    output_dir: Path
    base_model: str
    text_column: str
    label_column: str
    epochs: float
    batch_size: int
    learning_rate: float
    eval_ratio: float
    seed: int
    min_examples: int
    min_examples_per_label: int
    use_class_weights: bool


def normalize_label(value: str) -> str:
    """
    Normalizes dataset labels to the backend verdict labels.

    Args:
        value (str): Raw CSV label.

    Returns:
        str: Normalized label.
    """
    normalized = value.strip().lower()
    if normalized not in LABEL_ALIASES:
        raise ValueError(f"Unsupported label: {value}")
    return LABEL_ALIASES[normalized]


def read_training_rows(
    dataset_path: Path,
    text_column: str,
    label_column: str,
) -> list[dict[str, str]]:
    """
    Reads and validates training rows from a CSV file.

    Args:
        dataset_path (Path): CSV dataset path.
        text_column (str): Text column name.
        label_column (str): Label column name.

    Returns:
        list[dict[str, str]]: Normalized training rows.
    """
    rows: list[dict[str, str]] = []
    with dataset_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if text_column not in (reader.fieldnames or []):
            raise ValueError(f"Missing text column: {text_column}")
        if label_column not in (reader.fieldnames or []):
            raise ValueError(f"Missing label column: {label_column}")

        for row in reader:
            text = (row.get(text_column) or "").strip()
            label = (row.get(label_column) or "").strip()
            if not text or not label:
                continue
            rows.append({"text": text, "label": normalize_label(label)})

    if len(rows) < 4:
        raise ValueError("Training dataset must contain at least 4 valid rows.")

    return rows


def summarize_label_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    """
    Counts normalized labels in training rows.

    Args:
        rows (list[dict[str, str]]): Normalized training rows.

    Returns:
        dict[str, int]: Count per label.
    """
    counts = Counter(row["label"] for row in rows)
    return {"REAL": counts.get("REAL", 0), "FAKE": counts.get("FAKE", 0)}


def validate_training_quality(
    rows: list[dict[str, str]],
    min_examples: int,
    min_examples_per_label: int,
) -> None:
    """
    Validates whether a dataset is large enough for useful fine-tuning.

    Args:
        rows (list[dict[str, str]]): Normalized training rows.
        min_examples (int): Minimum total examples.
        min_examples_per_label (int): Minimum examples per label.
    """
    counts = summarize_label_counts(rows)

    if len(rows) < min_examples:
        raise ValueError(
            f"Training dataset has {len(rows)} rows. A stronger model needs "
            f"at least {min_examples} rows. Use --min-examples 4 only for a "
            "smoke test, not for a real checkpoint."
        )

    for label, count in counts.items():
        if count < min_examples_per_label:
            raise ValueError(
                f"Label {label} has {count} rows. A stronger model needs at "
                f"least {min_examples_per_label} rows per label."
            )


def train_roberta(config: TrainingConfig) -> None:
    """
    Fine-tunes and saves a RoBERTa sequence-classification checkpoint.

    Args:
        config (TrainingConfig): Training configuration.
    """
    try:
        import numpy as np
        # pyrefly: ignore [missing-import]
        from datasets import ClassLabel, Dataset, Features, Value
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Training requires datasets, numpy, torch, and transformers. "
            "Install backend requirements before training."
        ) from exc

    rows = read_training_rows(
        config.dataset_path,
        config.text_column,
        config.label_column,
    )
    validate_training_quality(
        rows,
        config.min_examples,
        config.min_examples_per_label,
    )
    id_to_label = {0: "REAL", 1: "FAKE"}
    label_to_id = {"REAL": 0, "FAKE": 1}
    label_counts = summarize_label_counts(rows)
    features = Features({
        "text": Value("string"),
        "label": ClassLabel(names=["REAL", "FAKE"])
    })
    dataset = Dataset.from_list(
        [
            {"text": row["text"], "label": label_to_id[row["label"]]}
            for row in rows
        ],
        features=features
    )
    # Calculate expected test set size. If it's smaller than the number of classes (2),
    # we disable stratification to avoid a ValueError from the datasets library.
    import math
    test_size_samples = math.ceil(len(dataset) * config.eval_ratio)
    stratify_column = "label" if test_size_samples >= 2 else None

    split_dataset = dataset.train_test_split(
        test_size=config.eval_ratio,
        seed=config.seed,
        stratify_by_column=stratify_column,
    )
    tokenizer = AutoTokenizer.from_pretrained(config.base_model)

    def tokenize_batch(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return tokenizer(batch["text"], truncation=True, max_length=512)

    tokenized_dataset = split_dataset.map(tokenize_batch, batched=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        config.base_model,
        num_labels=2,
        id2label=id_to_label,
        label2id=label_to_id,
    )
    training_args = TrainingArguments(
        output_dir=str(config.output_dir),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size,
        num_train_epochs=config.epochs,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        seed=config.seed,
        report_to=[],
    )

    def compute_metrics(eval_prediction: Any) -> dict[str, float]:
        logits, labels = eval_prediction
        predictions = np.argmax(logits, axis=-1)
        accuracy = float((predictions == labels).mean())
        return {
            "accuracy": accuracy,
            **_classification_metrics(predictions, labels),
        }

    trainer_class = _build_weighted_trainer_class(label_counts) if config.use_class_weights else Trainer
    trainer = trainer_class(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["test"],
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )
    trainer.train()
    trainer.save_model(str(config.output_dir))
    tokenizer.save_pretrained(str(config.output_dir))


def _classification_metrics(
    predictions: Any,
    labels: Any,
) -> dict[str, float]:
    """
    Computes macro precision, recall, and F1 for binary labels.

    Args:
        predictions (Any): Predicted label IDs.
        labels (Any): Gold label IDs.

    Returns:
        dict[str, float]: Macro classification metrics.
    """
    label_ids = [0, 1]
    precision_values: list[float] = []
    recall_values: list[float] = []
    f1_values: list[float] = []

    for label_id in label_ids:
        true_positive = int(((predictions == label_id) & (labels == label_id)).sum())
        false_positive = int(((predictions == label_id) & (labels != label_id)).sum())
        false_negative = int(((predictions != label_id) & (labels == label_id)).sum())
        precision = _safe_divide(true_positive, true_positive + false_positive)
        recall = _safe_divide(true_positive, true_positive + false_negative)
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        precision_values.append(precision)
        recall_values.append(recall)
        f1_values.append(f1)

    return {
        "precision_macro": sum(precision_values) / len(precision_values),
        "recall_macro": sum(recall_values) / len(recall_values),
        "f1_macro": sum(f1_values) / len(f1_values),
    }


def _safe_divide(numerator: float, denominator: float) -> float:
    """
    Divides two numbers while safely handling zero denominators.

    Args:
        numerator (float): Numerator.
        denominator (float): Denominator.

    Returns:
        float: Division result or 0.
    """
    if denominator == 0:
        return 0.0
    return float(numerator / denominator)


def _build_weighted_trainer_class(label_counts: dict[str, int]) -> type[Any]:
    """
    Builds a Trainer subclass that applies inverse-frequency class weights.

    Args:
        label_counts (dict[str, int]): Count per normalized label.

    Returns:
        type[Any]: Weighted Trainer subclass.
    """
    import torch
    from transformers import Trainer

    real_count = max(label_counts["REAL"], 1)
    fake_count = max(label_counts["FAKE"], 1)
    total_count = real_count + fake_count
    class_weights = torch.tensor(
        [
            total_count / (2 * real_count),
            total_count / (2 * fake_count),
        ],
        dtype=torch.float,
    )

    class WeightedTrainer(Trainer):
        """
        Trainer with weighted cross-entropy for imbalanced labels.
        """

        def compute_loss(
            self,
            model: Any,
            inputs: dict[str, Any],
            return_outputs: bool = False,
            num_items_in_batch: Any = None,
        ) -> Any:
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            weights = class_weights.to(outputs.logits.device)
            loss_function = torch.nn.CrossEntropyLoss(weight=weights)
            loss = loss_function(
                outputs.logits.view(-1, model.config.num_labels),
                labels.view(-1),
            )
            return (loss, outputs) if return_outputs else loss

    return WeightedTrainer


def parse_args() -> TrainingConfig:
    """
    Parses command-line arguments into a training config.

    Returns:
        TrainingConfig: Parsed config.
    """
    parser = argparse.ArgumentParser(description="Fine-tune RoBERTa for fake news detection.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-model", default="roberta-base")
    parser.add_argument("--text-column", default="text")
    parser.add_argument("--label-column", default="label")
    parser.add_argument("--epochs", default=3.0, type=float)
    parser.add_argument("--batch-size", default=8, type=int)
    parser.add_argument("--learning-rate", default=2e-5, type=float)
    parser.add_argument("--eval-ratio", default=0.2, type=float)
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--min-examples", default=100, type=int)
    parser.add_argument("--min-examples-per-label", default=40, type=int)
    parser.add_argument("--disable-class-weights", action="store_true")
    args = parser.parse_args()

    return TrainingConfig(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        base_model=args.base_model,
        text_column=args.text_column,
        label_column=args.label_column,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        eval_ratio=args.eval_ratio,
        seed=args.seed,
        min_examples=args.min_examples,
        min_examples_per_label=args.min_examples_per_label,
        use_class_weights=not args.disable_class_weights,
    )


if __name__ == "__main__":
    train_roberta(parse_args())
