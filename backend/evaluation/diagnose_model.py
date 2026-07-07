"""Quick diagnostic: prints raw logits to check if model is trained."""
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

tok = AutoTokenizer.from_pretrained("checkpoints/roberta-fake-news")
model = AutoModelForSequenceClassification.from_pretrained("checkpoints/roberta-fake-news")
model.eval()

samples = [
    "Bitcoin surged 5% to $45000 amid institutional inflows.",
    "Aliens are controlling the stock market through 5G towers.",
    "The Federal Reserve raised interest rates by 25 basis points.",
    "BREAKING: Send 1 BTC get 5 back! Limited giveaway!",
    "Reuters: Goldman Sachs reports Q3 earnings beat expectations.",
    "Secret government plot to ban all cryptocurrency revealed by whistleblower.",
]

print("=== RAW LOGITS DIAGNOSTIC ===")
print(f"id2label: {model.config.id2label}")
print()

with torch.no_grad():
    for s in samples:
        inputs = tok(s, return_tensors="pt", truncation=True, max_length=512)
        outputs = model(**inputs)
        logits = outputs.logits[0].tolist()
        probs = torch.softmax(outputs.logits, dim=-1)[0].tolist()
        pred = max(range(len(probs)), key=lambda i: probs[i])
        print(f"Logits: {[round(l, 4) for l in logits]}")
        print(f"Softmax: REAL={round(probs[0], 4)} FAKE={round(probs[1], 4)} -> Predicted: {model.config.id2label[pred]}")
        print(f"Text: {s}")
        print()
