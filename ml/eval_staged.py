"""
Staged compute efficiency analysis.
Quantifies what % of emails trigger Stage 2 at each threshold.
Direct evidence for the patent's "conditional computation" claim.
Saves: evaluation/results/staged_efficiency.json
"""

import json
import numpy as np
import onnxruntime as ort
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from tokenizers import BertWordPieceTokenizer

#  Paths 
CORPUS_PATH = Path("ml/data_processed/email_corpus.jsonl")
BINARY_ONNX = Path("ml/export/onnx/phish_binary.onnx")
VOCAB_PATH  = Path("ml/export/onnx/vocab.txt")
RESULTS_DIR = Path("evaluation/results")

THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40,
              0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
CANONICAL_TAUS = {0.25, 0.90}


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

    tok     = load_tokenizer()
    session = ort.InferenceSession(str(BINARY_ONNX),
                                   providers=["CPUExecutionProvider"])

    # 3 warmup passes
    first_text = test_df.loc[0, "text"]
    first_ids, first_attn = tokenize(first_text, tok)
    first_feeds = {"input_ids": first_ids, "attention_mask": first_attn}
    for _ in range(3):
        session.run(None, first_feeds)

    # Score all test emails
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

    # Compute per-threshold stats
    trigger_counts = []
    trigger_rates  = []
    stage1_rates   = []
    savings_pcts   = []

    for tau in THRESHOLDS:
        n_trigger    = int((scores_arr >= tau).sum())
        trigger_rate = n_trigger / n_total
        stage1_rate  = 1.0 - trigger_rate
        savings_pct  = stage1_rate * 100.0

        trigger_counts.append(n_trigger)
        trigger_rates.append(round(trigger_rate, 6))
        stage1_rates.append(round(stage1_rate, 6))
        savings_pcts.append(round(savings_pct, 4))

        print(f"  τ={tau:.2f}  trigger={n_trigger} ({trigger_rate:.2%})  "
              f"savings={savings_pct:.2f}%")

    # Canonical operating points
    canonical = {}
    for tau_val in sorted(CANONICAL_TAUS):
        tau_idx = THRESHOLDS.index(tau_val)
        label   = "research/SOUPS operating point" if tau_val == 0.25 else "production deployment operating point"
        canonical[f"tau_{tau_val:.2f}"] = {
            "stage2_trigger_rate": trigger_rates[tau_idx],
            "stage1_only_rate":    stage1_rates[tau_idx],
            "compute_savings_pct": savings_pcts[tau_idx],
            "note": label,
        }

    result = {
        "total_emails":         n_total,
        "model":                "phish_binary.onnx",
        "thresholds":           THRESHOLDS,
        "stage2_trigger_count": trigger_counts,
        "stage2_trigger_rate":  trigger_rates,
        "stage1_only_rate":     stage1_rates,
        "compute_savings_pct":  savings_pcts,
        "canonical_operating_points": canonical,
    }

    save_results(result, "staged_efficiency.json")

    print("\n=== Canonical Operating Points ===")
    for tau_key, vals in canonical.items():
        print(f"  {tau_key}: trigger={vals['stage2_trigger_rate']:.2%}  "
              f"savings={vals['compute_savings_pct']:.2f}%")


if __name__ == "__main__":
    main()
