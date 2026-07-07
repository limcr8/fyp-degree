import pytest

from training.train_roberta import normalize_label, read_training_rows


def test_normalize_label_accepts_supported_aliases() -> None:
    """
    Verifies label normalization for common dataset values.
    """
    assert normalize_label("real") == "REAL"
    assert normalize_label("0") == "REAL"
    assert normalize_label("fake") == "FAKE"
    assert normalize_label("1") == "FAKE"


def test_normalize_label_rejects_unknown_values() -> None:
    """
    Verifies unsupported labels fail clearly.
    """
    with pytest.raises(ValueError, match="Unsupported label"):
        normalize_label("satire")


def test_read_training_rows_validates_and_normalizes_csv(tmp_path) -> None:
    """
    Verifies CSV parsing keeps valid rows and normalizes labels.
    """
    dataset_path = tmp_path / "training.csv"
    dataset_path.write_text(
        "text,label\n"
        "Bitcoin ETF approved,real\n"
        "Secret 100x coin guaranteed,fake\n"
        "SEC publishes market update,0\n"
        "Risk-free crypto profit,1\n",
        encoding="utf-8",
    )

    rows = read_training_rows(dataset_path, "text", "label")

    assert rows == [
        {"text": "Bitcoin ETF approved", "label": "REAL"},
        {"text": "Secret 100x coin guaranteed", "label": "FAKE"},
        {"text": "SEC publishes market update", "label": "REAL"},
        {"text": "Risk-free crypto profit", "label": "FAKE"},
    ]
