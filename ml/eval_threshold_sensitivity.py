"""
Threshold sensitivity analysis.
Sweeps thresholds to show P/R/FPR tradeoff.
Also computes ROC-AUC and PR-AUC.
Saves: evaluation/results/threshold_sensitivity.json
"""

import json
import numpy as np
import onnxruntime as ort
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_curve, auc,
    precision_recall_curve, average_precision_score,
    confusion_matrix,
)
from tokenizers import BertWordPieceTokenizer

#  Paths 
CORPUS_PATH = Path("ml/data_processed/email_corpus.jsonl")
BINARY_ONNX = Path("ml/export/onnx/phish_binary.onnx")
VOCAB_PATH  = Path("ml/export/onnx/vocab.txt")
RESULTS_DIR = Path("evaluation/results")

THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40,
              0.50, 0.60, 0.70, 0.80, 0.90, 0.95]

CANONICAL_LABELS = {
    0.25: "research operating point",
    0.90: "production deployment operating point",
}


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


def metrics_at_threshold(y_true, scores, tau):
    y_pred = (scores >= tau).astype(int)
    cm     = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    n_neg = tn + fp
    n_pos = tp + fn
    p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r  = tp / n_pos      if n_pos > 0      else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    fpr = fp / n_neg          if n_neg > 0   else 0.0
    return {
        "threshold": tau,
        "precision": round(float(p),   4),
        "recall":    round(float(r),   4),
        "f1":        round(float(f1),  4),
        "fpr":       round(float(fpr), 6),
        "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
    }


def save_results(data: dict, filename: str):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {path}")


#  Main 

def main():
    print("Loading corpus …")
    df = load_corpus()
    _, test_df = train_test_split(
        df,
        test_size=0.20,
        stratify=df["label_phish"],
        random_state=42,
    )
    test_df = test_df.reset_index(drop=True)
    n_total = len(test_df)
    y_true  = test_df["label_phish"].values
    print(f"Test set: {n_total} emails")

    tok     = load_tokenizer()
    session = ort.InferenceSession(str(BINARY_ONNX),
                                   providers=["CPUExecutionProvider"])

    # No warmup needed for sensitivity analysis — just inference
    print("Scoring all test emails …")
    scores = []
    for i, row in test_df.iterrows():
        input_ids, attn = tokenize(row["text"], tok)
        feeds  = {"input_ids": input_ids, "attention_mask": attn}
        logits = session.run(None, feeds)[0][0]
        scores.append(float(softmax2(logits)))
        if (i + 1) % 1000 == 0:
            print(f"  … {i + 1}/{n_total}")

    scores_arr = np.array(scores)

    #  Threshold sweep 
    sweep = []
    for tau in THRESHOLDS:
        entry = metrics_at_threshold(y_true, scores_arr, tau)
        if tau in CANONICAL_LABELS:
            entry["canonical"] = True
            entry["label"]     = CANONICAL_LABELS[tau]
        else:
            entry["canonical"] = False
        sweep.append(entry)
        print(f"  τ={tau:.2f}  P={entry['precision']}  R={entry['recall']}  "
              f"F1={entry['f1']}  FPR={entry['fpr']}")

    #  ROC curve 
    fpr_arr, tpr_arr, _ = roc_curve(y_true, scores_arr)
    roc_auc_val = float(auc(fpr_arr, tpr_arr))

    #  PR curve 
    prec_arr, rec_arr, _ = precision_recall_curve(y_true, scores_arr)
    pr_auc_val = float(average_precision_score(y_true, scores_arr))

    # Downsample ROC/PR arrays (they can be very large) to 500 points
    def downsample(arr, n=500):
        if len(arr) <= n:
            return [round(float(v), 6) for v in arr]
        idx = np.linspace(0, len(arr) - 1, n, dtype=int)
        return [round(float(arr[i]), 6) for i in idx]

    result = {
        "model":     "phish_binary.onnx",
        "test_size": n_total,
        "threshold_sweep": sweep,
        "roc_auc": round(roc_auc_val, 6),
        "pr_auc":  round(pr_auc_val,  6),
        "roc_curve": {
            "fpr": downsample(fpr_arr),
            "tpr": downsample(tpr_arr),
        },
        "pr_curve": {
            "precision": downsample(prec_arr),
            "recall":    downsample(rec_arr),
        },
    }

    save_results(result, "threshold_sensitivity.json")

    print(f"\n  ROC-AUC = {roc_auc_val:.6f}")
    print(f"  PR-AUC  = {pr_auc_val:.6f}")


if __name__ == "__main__":
    main()
