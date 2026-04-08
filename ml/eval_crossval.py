"""
5-fold stratified cross-validation.
We cross-validate the scoring function over the full corpus, not retrain per fold.
Saves: evaluation/results/crossval.json
"""

import json
import numpy as np
import onnxruntime as ort
import pandas as pd
from pathlib import Path
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
from tokenizers import BertWordPieceTokenizer

#  Paths 
CORPUS_PATH = Path("ml/data_processed/email_corpus.jsonl")
BINARY_ONNX = Path("ml/export/onnx/phish_binary.onnx")
VOCAB_PATH  = Path("ml/export/onnx/vocab.txt")
RESULTS_DIR = Path("evaluation/results")

THRESHOLD  = 0.25
N_FOLDS    = 5


#  Helpers 

def load_corpus():
    rows = []
    with open(CORPUS_PATH) as f:
        for line in f:
            rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    df["label_phish"] = df["label_phish"].astype(int)
    df["text"] = df["subject"].fillna("") + "\n" + df["body"].fillna("")
    return df


def load_tokenizer():
    tok = BertWordPieceTokenizer(str(VOCAB_PATH), lowercase=True)
    tok.enable_truncation(max_length=256)
    tok.enable_padding(length=256)
    return tok


def tokenize(text: str, tok, max_len: int = 256):
    enc = tok.encode(text)
    input_ids      = np.array(enc.ids,            dtype=np.int64).reshape(1, max_len)
    attention_mask = np.array(enc.attention_mask, dtype=np.int64).reshape(1, max_len)
    return input_ids, attention_mask


def softmax2(logits):
    a, b = logits[0], logits[1]
    mx = max(a, b)
    ea, eb = np.exp(a - mx), np.exp(b - mx)
    return eb / (ea + eb)


def score_fold(session, tok, texts):
    """Return phish probability for each text."""
    scores = []
    for text in texts:
        input_ids, attn = tokenize(text, tok)
        feeds  = {"input_ids": input_ids, "attention_mask": attn}
        logits = session.run(None, feeds)[0][0]
        scores.append(float(softmax2(logits)))
    return np.array(scores)


def compute_metrics(y_true, y_pred):
    p  = float(precision_score(y_true, y_pred, zero_division=0))
    r  = float(recall_score(y_true, y_pred, zero_division=0))
    f  = float(f1_score(y_true, y_pred, zero_division=0))
    cm = confusion_matrix(y_true, y_pred)
    tn, fp = int(cm[0, 0]), int(cm[0, 1])
    n_neg  = tn + fp
    fpr    = fp / n_neg if n_neg > 0 else 0.0
    return round(p, 4), round(r, 4), round(f, 4), round(fpr, 6)


def save_results(data: dict, filename: str):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {path}")


#  Main 

def main():
    print("Loading full corpus …")
    df     = load_corpus()
    texts  = df["text"].tolist()
    labels = df["label_phish"].values
    print(f"Full corpus: {len(df)} emails "
          f"({labels.sum()} phishing, {(labels == 0).sum()} benign)")

    tok     = load_tokenizer()
    session = ort.InferenceSession(str(BINARY_ONNX),
                                   providers=["CPUExecutionProvider"])

    # 3 warmup passes
    first_ids, first_attn = tokenize(texts[0], tok)
    first_feeds = {"input_ids": first_ids, "attention_mask": first_attn}
    for _ in range(3):
        session.run(None, first_feeds)

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)

    per_fold = []
    for fold_idx, (_, test_idx) in enumerate(skf.split(texts, labels), start=1):
        fold_texts  = [texts[i] for i in test_idx]
        fold_labels = labels[test_idx]

        print(f"\nFold {fold_idx}/{N_FOLDS}: {len(fold_texts)} samples "
              f"({fold_labels.sum()} phishing) …")

        scores    = score_fold(session, tok, fold_texts)
        y_pred    = (scores >= THRESHOLD).astype(int)
        p, r, f, fpr = compute_metrics(fold_labels, y_pred)

        per_fold.append({
            "fold":      fold_idx,
            "precision": p,
            "recall":    r,
            "f1":        f,
            "fpr":       fpr,
            "n_samples": int(len(fold_texts)),
        })
        print(f"  P={p}  R={r}  F1={f}  FPR={fpr}")

    # Mean and std
    metrics_arr = {
        "precision": [x["precision"] for x in per_fold],
        "recall":    [x["recall"]    for x in per_fold],
        "f1":        [x["f1"]        for x in per_fold],
        "fpr":       [x["fpr"]       for x in per_fold],
    }
    mean = {k: round(float(np.mean(v)), 4) for k, v in metrics_arr.items()}
    std  = {k: round(float(np.std(v)),  4) for k, v in metrics_arr.items()}

    result = {
        "n_folds":   N_FOLDS,
        "threshold": THRESHOLD,
        "model":     "phish_binary.onnx",
        "per_fold":  per_fold,
        "mean":      mean,
        "std":       std,
    }

    save_results(result, "crossval.json")

    print(f"\n=== Cross-Validation Summary ({N_FOLDS}-fold) ===")
    print(f"  P = {mean['precision']} ± {std['precision']}")
    print(f"  R = {mean['recall']}    ± {std['recall']}")
    print(f"  F1= {mean['f1']}        ± {std['f1']}")
    print(f"  FPR={mean['fpr']}       ± {std['fpr']}")


if __name__ == "__main__":
    main()
