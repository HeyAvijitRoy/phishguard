"""
Full pipeline latency measurement.
Stage 1 (phish_binary.onnx) for ALL test emails.
Stage 2 (phish_intent.onnx) for emails passing τ=0.90 and τ=0.25 gates.
3 warmup passes before any measurement.
Saves:
  evaluation/results/full_pipeline_latency.json
  evaluation/results/stage1_latency.csv
  evaluation/results/stage2_latency_tau090.csv
"""

import json
import time
import csv
import numpy as np
import onnxruntime as ort
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from tokenizers import BertWordPieceTokenizer

#  Paths 
CORPUS_PATH = Path("ml/data_processed/email_corpus.jsonl")
BINARY_ONNX = Path("ml/export/onnx/phish_binary.onnx")
INTENT_ONNX = Path("ml/export/onnx/phish_intent.onnx")
VOCAB_PATH  = Path("ml/export/onnx/vocab.txt")
RESULTS_DIR = Path("evaluation/results")

TAU_RESEARCH    = 0.25
TAU_PRODUCTION  = 0.90


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


def latency_stats(times_ms: list) -> dict:
    arr = np.array(times_ms)
    return {
        "mean_ms":   round(float(np.mean(arr)),               4),
        "median_ms": round(float(np.median(arr)),             4),
        "p95_ms":    round(float(np.percentile(arr, 95)),     4),
        "p99_ms":    round(float(np.percentile(arr, 99)),     4),
        "max_ms":    round(float(np.max(arr)),                4),
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
    print(f"Test set: {n_total} emails")

    tok      = load_tokenizer()
    sess_bin = ort.InferenceSession(str(BINARY_ONNX),
                                    providers=["CPUExecutionProvider"])
    sess_int = ort.InferenceSession(str(INTENT_ONNX),
                                    providers=["CPUExecutionProvider"])

    #  3 warmup passes on binary model 
    first_ids, first_attn = tokenize(test_df.loc[0, "text"], tok)
    bin_warmup_feeds = {"input_ids": first_ids, "attention_mask": first_attn}
    for _ in range(3):
        sess_bin.run(None, bin_warmup_feeds)

    #  3 warmup passes on intent model 
    for _ in range(3):
        sess_int.run(None, bin_warmup_feeds)

    print("\nMeasuring Stage 1 latency for all test emails …")

    stage1_latencies: list[float] = []   # ms per email
    scores:           list[float] = []

    for i, row in test_df.iterrows():
        input_ids, attn = tokenize(row["text"], tok)
        feeds = {"input_ids": input_ids, "attention_mask": attn}

        t0     = time.perf_counter()
        logits = sess_bin.run(None, feeds)[0][0]
        lat_s1 = (time.perf_counter() - t0) * 1000

        stage1_latencies.append(lat_s1)
        scores.append(float(softmax2(logits)))

        if (i + 1) % 1000 == 0:
            print(f"  … {i + 1}/{n_total}")

    scores_arr = np.array(scores)
    labels_arr = test_df["label_phish"].values

    #  Stage 2 latency at τ=0.90 
    idx_tau090 = np.where(scores_arr >= TAU_PRODUCTION)[0]
    print(f"\nStage 2 at τ=0.90: {len(idx_tau090)} emails triggered …")

    stage2_latencies_090: list[tuple[int, float]] = []   # (email_idx, ms)
    combined_lat_090:     list[float] = []

    for i in idx_tau090:
        input_ids, attn = tokenize(test_df.loc[i, "text"], tok)
        feeds = {"input_ids": input_ids, "attention_mask": attn}
        t0    = time.perf_counter()
        sess_int.run(None, feeds)
        lat_s2 = (time.perf_counter() - t0) * 1000
        stage2_latencies_090.append((int(i), round(lat_s2, 4)))
        combined_lat_090.append(stage1_latencies[i] + lat_s2)

    #  Stage 2 latency at τ=0.25 
    idx_tau025 = np.where(scores_arr >= TAU_RESEARCH)[0]
    print(f"Stage 2 at τ=0.25: {len(idx_tau025)} emails triggered …")

    stage2_latencies_025: list[float] = []

    for i in idx_tau025:
        input_ids, attn = tokenize(test_df.loc[i, "text"], tok)
        feeds = {"input_ids": input_ids, "attention_mask": attn}
        t0    = time.perf_counter()
        sess_int.run(None, feeds)
        stage2_latencies_025.append((time.perf_counter() - t0) * 1000)

    #  Save CSVs 
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    stage1_csv = RESULTS_DIR / "stage1_latency.csv"
    with open(stage1_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["email_idx", "latency_ms", "label"])
        for i, lat in enumerate(stage1_latencies):
            writer.writerow([i, round(lat, 4), int(labels_arr[i])])
    print(f"Saved: {stage1_csv}")

    stage2_csv = RESULTS_DIR / "stage2_latency_tau090.csv"
    with open(stage2_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["email_idx", "latency_ms", "label"])
        for idx, lat in stage2_latencies_090:
            writer.writerow([idx, lat, int(labels_arr[idx])])
    print(f"Saved: {stage2_csv}")

    #  Build JSON output 
    s1_stats = latency_stats(stage1_latencies)
    s1_stats["n_emails"] = n_total
    s1_stats["note"] = "ONNX session.run() only, 3 warmup, CPU"

    s2_025 = latency_stats(stage2_latencies_025) if stage2_latencies_025 else {}
    s2_025["n_emails_triggered"] = int(len(idx_tau025))
    s2_025["trigger_rate"]       = round(len(idx_tau025) / n_total, 6)

    s2_090 = latency_stats([lat for _, lat in stage2_latencies_090]) if stage2_latencies_090 else {}
    s2_090["n_emails_triggered"] = int(len(idx_tau090))
    s2_090["trigger_rate"]       = round(len(idx_tau090) / n_total, 6)

    comb_090 = latency_stats(combined_lat_090) if combined_lat_090 else {}
    comb_090["n_emails"] = int(len(combined_lat_090))
    comb_090["note"]     = "Stage 1 + Stage 2 for gate-passed emails only"

    result = {
        "stage1":                     s1_stats,
        "stage2_at_tau_0.25":         s2_025,
        "stage2_at_tau_0.90":         s2_090,
        "combined_pipeline_at_tau_0.90": comb_090,
    }

    save_results(result, "full_pipeline_latency.json")

    print("\n=== Pipeline Latency Summary ===")
    print(f"  Stage 1 mean={s1_stats['mean_ms']:.2f}ms  P95={s1_stats['p95_ms']:.2f}ms")
    if stage2_latencies_025:
        print(f"  Stage 2 @τ=0.25 mean={s2_025['mean_ms']:.2f}ms  "
              f"triggered={s2_025['n_emails_triggered']} ({s2_025['trigger_rate']:.2%})")
    if stage2_latencies_090:
        print(f"  Stage 2 @τ=0.90 mean={s2_090['mean_ms']:.2f}ms  "
              f"triggered={s2_090['n_emails_triggered']} ({s2_090['trigger_rate']:.2%})")
    if combined_lat_090:
        print(f"  Combined @τ=0.90 mean={comb_090['mean_ms']:.2f}ms  "
              f"P95={comb_090['p95_ms']:.2f}ms")


if __name__ == "__main__":
    main()
