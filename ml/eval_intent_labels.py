"""
Per-label P/R/F1 for all 4 intent classes.
Intent labels are merged from train_intent.jsonl + val_intent.jsonl (by email ID).
Ham emails receive all-zero intent labels by construction.
Saves: evaluation/results/intent_labels_eval.json
"""

import json
import numpy as np
import onnxruntime as ort
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_fscore_support
from tokenizers import BertWordPieceTokenizer

#  Paths 
CORPUS_PATH   = Path("ml/data_processed/email_corpus.jsonl")
INTENT_PATHS  = [
    Path("ml/data_processed/train_intent.jsonl"),
    Path("ml/data_processed/val_intent.jsonl"),
]
BINARY_ONNX   = Path("ml/export/onnx/phish_binary.onnx")
INTENT_ONNX   = Path("ml/export/onnx/phish_intent.onnx")
VOCAB_PATH    = Path("ml/export/onnx/vocab.txt")
RESULTS_DIR   = Path("evaluation/results")

INTENT_LABEL_NAMES = [
    "credential_harvesting",
    "payment_fraud",
    "threat_language",
    "impersonation",
]
INTENT_COL_NAMES = [
    "intent_credential",
    "intent_payment",
    "intent_threat",
    "intent_impersonation",
]
THRESHOLD = 0.5


#  Helpers 

def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def load_corpus():
    rows = []
    with open(CORPUS_PATH) as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def load_intent_lookup() -> dict:
    """Return dict[email_id -> {intent_credential, intent_payment, ...}]."""
    lookup = {}
    for path in INTENT_PATHS:
        with open(path) as f:
            for line in f:
                row = json.loads(line)
                lookup[row["id"]] = {
                    "intent_credential":    int(row.get("intent_credential",    0)),
                    "intent_payment":       int(row.get("intent_payment",       0)),
                    "intent_threat":        int(row.get("intent_threat",        0)),
                    "intent_impersonation": int(row.get("intent_impersonation", 0)),
                }
    return lookup


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


def run_intent(session, input_ids, attention_mask):
    feeds = {"input_ids": input_ids, "attention_mask": attention_mask}
    logits = session.run(None, feeds)[0][0]   # shape [4]
    return sigmoid(logits)


def save_results(data: dict, filename: str):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {path}")


#  Main 

def main():
    print("Loading corpus and intent labels …")
    rows = load_corpus()
    intent_lookup = load_intent_lookup()

    import pandas as pd
    df = pd.DataFrame(rows)
    df["label_phish"] = df["label_phish"].astype(int)

    _, test_df = train_test_split(
        df,
        test_size=0.20,
        stratify=df["label_phish"],
        random_state=42,
    )
    test_df = test_df.reset_index(drop=True)
    print(f"Test set: {len(test_df)} emails "
          f"({test_df['label_phish'].sum()} phishing, "
          f"{(test_df['label_phish']==0).sum()} benign)")

    tok     = load_tokenizer()
    session = ort.InferenceSession(str(INTENT_ONNX),
                                   providers=["CPUExecutionProvider"])

    #  Phase 1: phishing-only evaluation 
    phish_df = test_df[test_df["label_phish"] == 1].reset_index(drop=True)
    n_phish  = len(phish_df)
    print(f"\nRunning intent inference on {n_phish} phishing emails …")

    y_true = np.zeros((n_phish, 4), dtype=int)
    y_pred = np.zeros((n_phish, 4), dtype=int)

    for i, row in phish_df.iterrows():
        email_id = row["id"]
        text = f"{row.get('subject', '')}\n{row.get('body', '')}"
        input_ids, attn = tokenize(text, tok)
        probs = run_intent(session, input_ids, attn)
        y_pred[i] = (probs >= THRESHOLD).astype(int)

        # Ground truth from intent lookup; default 0 if not found
        if email_id in intent_lookup:
            il = intent_lookup[email_id]
            y_true[i] = [
                il["intent_credential"],
                il["intent_payment"],
                il["intent_threat"],
                il["intent_impersonation"],
            ]
        # else remains 0

        if (i + 1) % 200 == 0:
            print(f"  … {i + 1}/{n_phish}")

    # Per-label metrics
    per_label = {}
    for j, label_name in enumerate(INTENT_LABEL_NAMES):
        p, r, f, _ = precision_recall_fscore_support(
            y_true[:, j], y_pred[:, j],
            average="binary", zero_division=0
        )
        per_label[label_name] = {
            "precision": round(float(p), 4),
            "recall":    round(float(r), 4),
            "f1":        round(float(f), 4),
            "support":   int(y_true[:, j].sum()),
        }

    # Micro avg
    p_micro, r_micro, f_micro, _ = precision_recall_fscore_support(
        y_true, y_pred, average="micro", zero_division=0
    )
    # Macro avg
    p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )

    # Co-occurrence matrix (4×4): how often labels i and j are BOTH predicted 1
    cooc = (y_pred.T @ y_pred).tolist()

    #  Phase 2: ham FPR per label 
    ham_df = test_df[test_df["label_phish"] == 0].reset_index(drop=True)
    n_ham  = len(ham_df)
    print(f"\nRunning intent inference on {n_ham} ham emails for FPR …")

    ham_fp_counts = np.zeros(4, dtype=int)

    for i, row in ham_df.iterrows():
        text = f"{row.get('subject', '')}\n{row.get('body', '')}"
        input_ids, attn = tokenize(text, tok)
        probs = run_intent(session, input_ids, attn)
        ham_fp_counts += (probs >= THRESHOLD).astype(int)

        if (i + 1) % 500 == 0:
            print(f"  … {i + 1}/{n_ham}")

    ham_fpr = {
        label_name: round(float(ham_fp_counts[j]) / n_ham, 6)
        for j, label_name in enumerate(INTENT_LABEL_NAMES)
    }

    #  Output 
    result = {
        "model":     "phish_intent.onnx",
        "threshold": THRESHOLD,
        "phish_only_eval": {
            "n_phishing_samples": n_phish,
            "labels": INTENT_LABEL_NAMES,
            "per_label": per_label,
            "micro_avg": {
                "precision": round(float(p_micro), 4),
                "recall":    round(float(r_micro), 4),
                "f1":        round(float(f_micro), 4),
            },
            "macro_avg": {
                "precision": round(float(p_macro), 4),
                "recall":    round(float(r_macro), 4),
                "f1":        round(float(f_macro), 4),
            },
            "label_cooccurrence": cooc,
        },
        "ham_fpr_per_label": ham_fpr,
        "label_methodology": (
            "keyword-derived weak labels via build_dataset.py:weak_label_intents"
        ),
        "ham_label_note": (
            "Ham emails receive all-zero intent labels by construction — "
            "ham FPR measured empirically"
        ),
    }

    save_results(result, "intent_labels_eval.json")

    print("\n=== Intent Label Eval Summary ===")
    for name, m in per_label.items():
        print(f"  {name:25s}  P={m['precision']:.4f}  R={m['recall']:.4f}  "
              f"F1={m['f1']:.4f}  support={m['support']}")
    print(f"  micro F1 = {result['phish_only_eval']['micro_avg']['f1']:.4f}")
    print(f"  macro F1 = {result['phish_only_eval']['macro_avg']['f1']:.4f}")
    print("\nHam FPR per label:")
    for name, fpr in ham_fpr.items():
        print(f"  {name:25s}  FPR={fpr:.4%}")


if __name__ == "__main__":
    main()
