#!/usr/bin/env python3
"""Binary phishing eval v2.
- Uses BertWordPieceTokenizer from vocab.txt (matches JavaScript runtime)
- 3 warmup passes before timing; times session.run() only
- Evaluates at both τ=0.25 and τ=0.90
- Canonical 80/20 stratified split, random_state=42
Writes: evaluation/results/binary_eval_v2.json
"""

import json
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from tokenizers import BertWordPieceTokenizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = PROJECT_ROOT / "ml"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
VOCAB_PATH = ML_ROOT / "export" / "onnx" / "vocab.txt"
ONNX_PATH = ML_ROOT / "export" / "onnx" / "phish_binary.onnx"
CORPUS_PATH = ML_ROOT / "data_processed" / "email_corpus.jsonl"


def load_corpus():
    rows = []
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def get_canonical_split(rows):
    """
    THE canonical split for all evaluation scripts.
    """
    labels = [int(r["label_phish"]) for r in rows]
    _, test_rows = train_test_split(
        rows,
        test_size=0.20,
        stratify=labels,
        random_state=42,
    )
    return test_rows


def load_tokenizer():
    tokenizer = BertWordPieceTokenizer(str(VOCAB_PATH), lowercase=True)
    tokenizer.enable_truncation(max_length=256)
    tokenizer.enable_padding(length=256)
    return tokenizer


def tokenize_all(rows, tokenizer):
    input_ids_list = []
    attention_mask_list = []
    labels_list = []
    for r in rows:
        text = f"{r.get('subject', '')}\n{r.get('body', '')}".strip()
        enc = tokenizer.encode(text)
        input_ids_list.append(np.array(enc.ids, dtype=np.int64).reshape(1, 256))
        attention_mask_list.append(
            np.array(enc.attention_mask, dtype=np.int64).reshape(1, 256)
        )
        labels_list.append(int(r["label_phish"]))
    return input_ids_list, attention_mask_list, labels_list


def softmax(logits):
    logits = np.asarray(logits, dtype=np.float64)
    e = np.exp(logits - np.max(logits))
    return e / e.sum()


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading corpus...")
    rows = load_corpus()
    test_rows = get_canonical_split(rows)

    labels_list = [int(r["label_phish"]) for r in test_rows]
    phish_count = sum(labels_list)
    benign_count = len(labels_list) - phish_count
    print(f"Test set: {len(test_rows)} samples  ({phish_count} phishing, {benign_count} benign)")

    print("Loading tokenizer (BertWordPieceTokenizer)...")
    tokenizer = load_tokenizer()

    print("Tokenizing test set...")
    input_ids_list, attention_mask_list, _ = tokenize_all(test_rows, tokenizer)

    print(f"Loading ONNX model: {ONNX_PATH}")
    session = ort.InferenceSession(str(ONNX_PATH))

    # 3 warmup passes on first sample (JIT compiles ONNX graph)
    print("Running 3 warmup passes...")
    warm_feeds = {
        "input_ids": input_ids_list[0],
        "attention_mask": attention_mask_list[0],
    }
    for _ in range(3):
        session.run(None, warm_feeds)

    # Timed inference on all test samples — session.run() only, no tokenization
    print(f"Running timed inference on {len(test_rows)} samples...")
    times_ms = []
    preds_prob = []
    for input_ids, attention_mask in zip(input_ids_list, attention_mask_list):
        feeds = {"input_ids": input_ids, "attention_mask": attention_mask}
        t0 = time.perf_counter()
        outputs = session.run(None, feeds)
        times_ms.append((time.perf_counter() - t0) * 1000)
        logits = outputs[0][0].tolist()
        probs = softmax(logits)
        preds_prob.append(float(probs[1]))  # index 1 = phishing class

    latency = {
        "mean_ms": round(float(np.mean(times_ms)), 3),
        "median_ms": round(float(np.median(times_ms)), 3),
        "p95_ms": round(float(np.percentile(times_ms, 95)), 3),
        "max_ms": round(float(max(times_ms)), 3),
        "n_warmup": 3,
        "note": "ONNX session.run() only",
    }

    # Metrics at both thresholds
    thresholds = [0.25, 0.90]
    threshold_results = {}
    confusion_matrices = {}

    for thresh in thresholds:
        preds_bin = [1 if p >= thresh else 0 for p in preds_prob]
        cm = confusion_matrix(labels_list, preds_bin, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        precision = precision_score(labels_list, preds_bin, zero_division=0)
        recall = recall_score(labels_list, preds_bin, zero_division=0)
        f1 = f1_score(labels_list, preds_bin, zero_division=0)
        fpr = float(fp) / (fp + tn) if (fp + tn) > 0 else 0.0
        key = str(thresh)
        threshold_results[key] = {
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "fpr": round(fpr, 4),
        }
        confusion_matrices[key] = [[int(tn), int(fp)], [int(fn), int(tp)]]
        print(
            f"  τ={thresh:.2f}  P={precision:.4f}  R={recall:.4f}  "
            f"F1={f1:.4f}  FPR={fpr:.4f}"
        )

    result = {
        "thresholds": threshold_results,
        "dataset_size": len(labels_list),
        "phishing_count": phish_count,
        "benign_count": benign_count,
        "confusion_matrices": confusion_matrices,
        "latency": latency,
        "tokenizer": "BertWordPieceTokenizer from vocab.txt",
        "split": "stratified 80/20 random_state=42",
    }

    out_path = RESULTS_DIR / "binary_eval_v2.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved: {out_path}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
