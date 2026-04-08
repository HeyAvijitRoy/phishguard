"""
Baseline comparison.
Compares PhishGuard binary ONNX against:
  1. TF-IDF + Logistic Regression
  2. TF-IDF + LinearSVC
  3. phish_binary.onnx without staging gate (every email scored, τ=0.25)
"""

import json
import time
import random
import numpy as np
import onnxruntime as ort
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
from tokenizers import BertWordPieceTokenizer

#  Paths 
CORPUS_PATH = Path("ml/data_processed/email_corpus.jsonl")
BINARY_ONNX = Path("ml/export/onnx/phish_binary.onnx")
VOCAB_PATH  = Path("ml/export/onnx/vocab.txt")
RESULTS_DIR = Path("evaluation/results")

THRESHOLD_ONNX = 0.25


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


def get_canonical_split(df):
    return train_test_split(
        df,
        test_size=0.20,
        stratify=df["label_phish"],
        random_state=42,
    )


def compute_metrics(y_true, y_pred):
    p  = float(precision_score(y_true, y_pred, zero_division=0))
    r  = float(recall_score(y_true, y_pred, zero_division=0))
    f  = float(f1_score(y_true, y_pred, zero_division=0))
    cm = confusion_matrix(y_true, y_pred)
    tn, fp = int(cm[0, 0]), int(cm[0, 1])
    n_neg  = tn + fp
    fpr    = fp / n_neg if n_neg > 0 else 0.0
    return {
        "precision": round(p, 4),
        "recall":    round(r, 4),
        "f1":        round(f, 4),
        "fpr":       round(fpr, 6),
    }


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


def run_binary_onnx(session, text, tok):
    input_ids, attn = tokenize(text, tok)
    feeds  = {"input_ids": input_ids, "attention_mask": attn}
    logits = session.run(None, feeds)[0][0]
    return float(softmax2(logits))


def measure_sklearn_latency(model, X_sample):
    """Mean ms/email over provided sample (no warmup needed for sklearn)."""
    times = []
    for i in range(len(X_sample)):
        t0 = time.perf_counter()
        model.predict(X_sample[i])
        times.append((time.perf_counter() - t0) * 1000)
    return float(np.mean(times))


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
    train_df, test_df = get_canonical_split(df)
    train_df = train_df.reset_index(drop=True)
    test_df  = test_df.reset_index(drop=True)
    print(f"Train: {len(train_df)}  |  Test: {len(test_df)}")

    y_train = train_df["label_phish"].values
    y_test  = test_df["label_phish"].values

    #  TF-IDF vectorizer (shared) 
    print("\nFitting TF-IDF vectorizer …")
    tfidf = TfidfVectorizer(max_features=50000, ngram_range=(1, 2), sublinear_tf=True)
    X_train = tfidf.fit_transform(train_df["text"])
    X_test  = tfidf.transform(test_df["text"])

    # Latency sample — 100 random test rows as single-row sparse matrices
    rng = random.Random(42)
    sample_idx = rng.sample(range(len(test_df)), 100)

    #  Baseline 1: TF-IDF + LogisticRegression 
    print("\nTraining Logistic Regression …")
    lr = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs", n_jobs=-1)
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)
    metrics_lr = compute_metrics(y_test, y_pred_lr)

    # Latency: 100 single-row predictions
    lat_lr_times = []
    for idx in sample_idx:
        x1 = X_test[idx]
        t0 = time.perf_counter()
        lr.predict(x1)
        lat_lr_times.append((time.perf_counter() - t0) * 1000)
    metrics_lr["mean_ms_per_email"] = round(float(np.mean(lat_lr_times)), 4)
    metrics_lr["train_samples"]     = int(len(train_df))
    print(f"  LR  P={metrics_lr['precision']}  R={metrics_lr['recall']}  "
          f"F1={metrics_lr['f1']}  FPR={metrics_lr['fpr']}  "
          f"lat={metrics_lr['mean_ms_per_email']:.3f}ms")

    #  Baseline 2: TF-IDF + LinearSVC 
    print("\nTraining LinearSVC …")
    svm = LinearSVC(C=1.0, max_iter=2000)
    svm.fit(X_train, y_train)
    y_pred_svm = svm.predict(X_test)
    metrics_svm = compute_metrics(y_test, y_pred_svm)

    lat_svm_times = []
    for idx in sample_idx:
        x1 = X_test[idx]
        t0 = time.perf_counter()
        svm.predict(x1)
        lat_svm_times.append((time.perf_counter() - t0) * 1000)
    metrics_svm["mean_ms_per_email"] = round(float(np.mean(lat_svm_times)), 4)
    metrics_svm["train_samples"]     = int(len(train_df))
    print(f"  SVM P={metrics_svm['precision']}  R={metrics_svm['recall']}  "
          f"F1={metrics_svm['f1']}  FPR={metrics_svm['fpr']}  "
          f"lat={metrics_svm['mean_ms_per_email']:.3f}ms")

    #  Baseline 3: ONNX non-staged (all emails, τ=0.25) 
    print("\nRunning ONNX non-staged baseline …")
    tok     = load_tokenizer()
    session = ort.InferenceSession(str(BINARY_ONNX),
                                   providers=["CPUExecutionProvider"])

    # 3 warmup passes on first sample
    first_text = test_df.loc[0, "text"]
    first_ids, first_attn = tokenize(first_text, tok)
    first_feeds = {"input_ids": first_ids, "attention_mask": first_attn}
    for _ in range(3):
        session.run(None, first_feeds)

    # Score all test emails
    scores_onnx = []
    for i, row in test_df.iterrows():
        text = row["text"]
        input_ids, attn = tokenize(text, tok)
        feeds  = {"input_ids": input_ids, "attention_mask": attn}
        logits = session.run(None, feeds)[0][0]
        scores_onnx.append(float(softmax2(logits)))

        if (i + 1) % 1000 == 0:
            print(f"  … {i + 1}/{len(test_df)}")

    y_pred_onnx = (np.array(scores_onnx) >= THRESHOLD_ONNX).astype(int)
    metrics_onnx = compute_metrics(y_test, y_pred_onnx)

    # Latency: 3 warmup already done; measure 100 samples
    lat_onnx_times = []
    for idx in sample_idx:
        text = test_df.loc[idx, "text"]
        inp_ids, attn = tokenize(text, tok)
        feeds = {"input_ids": inp_ids, "attention_mask": attn}
        t0 = time.perf_counter()
        session.run(None, feeds)
        lat_onnx_times.append((time.perf_counter() - t0) * 1000)

    metrics_onnx["mean_ms_per_email"] = round(float(np.mean(lat_onnx_times)), 4)
    metrics_onnx["threshold"]         = THRESHOLD_ONNX
    metrics_onnx["note"] = (
        "phish_binary.onnx, all emails run through, no staging gate"
    )
    print(f"  ONNX P={metrics_onnx['precision']}  R={metrics_onnx['recall']}  "
          f"F1={metrics_onnx['f1']}  FPR={metrics_onnx['fpr']}  "
          f"lat={metrics_onnx['mean_ms_per_email']:.3f}ms")

    #  Output 
    result = {
        "test_size": int(len(test_df)),
        "baselines": {
            "tfidf_lr":       metrics_lr,
            "tfidf_svm":      metrics_svm,
            "onnx_nonstaged": metrics_onnx,
        },
        "phishguard_staged": {
            "precision":       0.9866,
            "recall":          0.9916,
            "f1":              0.9891,
            "fpr":             0.0041,
            "threshold":       0.25,
            "mean_ms_stage1":  46.207,
            "note": "from binary_eval_v2.json — included for comparison",
        },
    }

    save_results(result, "baselines.json")
    print("\nDone.")


if __name__ == "__main__":
    main()
