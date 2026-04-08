#!/usr/bin/env python3
"""
Adversarial evaluation: test phish_binary.onnx against 200 LLM-generated
synthetic phishing emails.

Reads:  ml/data_raw/synthetic_phishing/synthetic_phishing_200.jsonl
        ml/export/onnx/phish_binary.onnx
        ml/export/onnx/vocab.txt
Writes: evaluation/results/adversarial_eval.json
"""

import json
import sys
import numpy as np
from pathlib import Path

SYNTHETIC_JSONL = Path("ml/data_raw/synthetic_phishing/synthetic_phishing_200.jsonl")
ONNX_PATH = Path("ml/export/onnx/phish_binary.onnx")
VOCAB_PATH = Path("ml/export/onnx/vocab.txt")
BINARY_EVAL_PATH = Path("evaluation/results/binary_eval_v2.json")
RESULTS_DIR = Path("evaluation/results")
OUTPUT_PATH = RESULTS_DIR / "adversarial_eval.json"

MAX_LEN = 256
THRESHOLDS = [0.25, 0.90]
INTENT_CATEGORIES = [
    "credential_harvesting",
    "payment_fraud",
    "threat_language",
    "impersonation",
]

INTENT_TO_FIELD = {
    "credential_harvesting": "intent_credential",
    "payment_fraud": "intent_payment",
    "threat_language": "intent_threat",
    "impersonation": "intent_impersonation",
}


def softmax(logits):
    max_l = max(logits)
    exps = [np.exp(v - max_l) for v in logits]
    total = sum(exps)
    return [e / total for e in exps]


def load_tokenizer():
    from tokenizers import BertWordPieceTokenizer
    tokenizer = BertWordPieceTokenizer(str(VOCAB_PATH), lowercase=True)
    tokenizer.enable_truncation(max_length=MAX_LEN)
    tokenizer.enable_padding(length=MAX_LEN)
    return tokenizer


def tokenize(text, tokenizer):
    enc = tokenizer.encode(text)
    input_ids = np.array(enc.ids, dtype=np.int64).reshape(1, MAX_LEN)
    attention_mask = np.array(enc.attention_mask, dtype=np.int64).reshape(1, MAX_LEN)
    return input_ids, attention_mask


def run_binary_inference(session, input_ids, attention_mask):
    feeds = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
    }
    logits = session.run(None, feeds)[0][0]
    probs = softmax(list(logits))
    return float(probs[1])  # P(phishing)


def interpret_delta(detection_rate, corpus_recall):
    if detection_rate >= 0.99:
        return ("LLM-generated phishing detected at near-identical rates to corpus phishing, "
                "indicating robustness against ChatGPT-generated content.")
    elif detection_rate >= 0.95:
        return ("LLM-generated phishing shows slightly reduced detection rate vs corpus phishing. "
                "Adversarial LLM content presents a marginal evasion advantage.")
    elif detection_rate >= 0.85:
        return ("LLM-generated phishing shows moderately reduced detection. "
                "Intent categories with lower detection warrant adversarial training in future work.")
    else:
        return ("LLM-generated phishing shows significant evasion. "
                "Adversarial training on synthetic data is recommended before deployment.")


def main():
    # --- Validate inputs ---
    for path in [SYNTHETIC_JSONL, ONNX_PATH, VOCAB_PATH]:
        if not path.exists():
            print(f"ERROR: Required file not found: {path}")
            if path == SYNTHETIC_JSONL:
                print("  Run ml/ingest_synthetic_phishing.py first.")
            sys.exit(1)

    # --- Load synthetic emails ---
    records = []
    with open(SYNTHETIC_JSONL) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"Loaded {len(records)} synthetic emails from {SYNTHETIC_JSONL}")

    # --- Load corpus recall for comparison ---
    corpus_recall_025 = 0.9916  # default from known results
    if BINARY_EVAL_PATH.exists():
        with open(BINARY_EVAL_PATH) as f:
            bev = json.load(f)
        corpus_recall_025 = bev["thresholds"]["0.25"]["recall"]

    # --- Load ONNX session ---
    import onnxruntime as ort
    session = ort.InferenceSession(
        str(ONNX_PATH),
        providers=["CPUExecutionProvider"],
    )

    # --- Load tokenizer ---
    tokenizer = load_tokenizer()

    # --- Warmup passes ---
    print("Warming up ONNX session (3 passes)...")
    warmup_text = "Your account has been suspended. Verify your credentials immediately."
    warmup_ids, warmup_mask = tokenize(warmup_text, tokenizer)
    for _ in range(3):
        session.run(None, {
            "input_ids": warmup_ids,
            "attention_mask": warmup_mask,
        })

    # --- Run inference ---
    print(f"Running inference on {len(records)} emails...")
    results = []
    for i, rec in enumerate(records):
        text = f"{rec.get('subject', '')} {rec.get('body', '')}"
        input_ids, attention_mask = tokenize(text, tokenizer)
        phish_prob = run_binary_inference(session, input_ids, attention_mask)
        results.append({
            "id": rec["id"],
            "phish_prob": phish_prob,
            "intent": rec.get("original_intent_label", "unknown"),
            "body_preview": rec.get("body", "")[:200],
            "generation_model": rec.get("generation_model", "unknown"),
        })
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(records)}")

    # --- Compute metrics at each threshold ---
    detection_rates_025 = None

    by_tau = {}
    by_intent_tau = {}

    TAU_KEYS = {0.25: "at_tau_0.25", 0.90: "at_tau_0.90"}

    for tau in THRESHOLDS:
        tau_key = TAU_KEYS[tau]
        detected = [r for r in results if r["phish_prob"] >= tau]
        missed = [r for r in results if r["phish_prob"] < tau]

        det_count = len(detected)
        miss_count = len(missed)
        total = len(results)
        detection_rate = det_count / total if total > 0 else 0.0

        by_tau[tau_key] = {
            "detected": det_count,
            "missed": miss_count,
            "detection_rate": round(detection_rate, 4),
            "attack_success_rate": round(1.0 - detection_rate, 4),
        }

        if tau == 0.25:
            detection_rates_025 = detection_rate

        # Per-intent breakdown
        tau_label = TAU_KEYS[tau]
        for intent in INTENT_CATEGORIES:
            intent_recs = [r for r in results if r["intent"] == intent]
            if not intent_recs:
                continue
            intent_detected = sum(1 for r in intent_recs if r["phish_prob"] >= tau)
            intent_total = len(intent_recs)
            if intent not in by_intent_tau:
                by_intent_tau[intent] = {}
            by_intent_tau[intent][tau_label] = {
                "detected": intent_detected,
                "missed": intent_total - intent_detected,
                "detection_rate": round(intent_detected / intent_total, 4),
            }

    # --- Missed emails at τ=0.25 (qualitative analysis) ---
    missed_025 = [
        {
            "id": r["id"],
            "phish_prob": round(r["phish_prob"], 4),
            "intent": r["intent"],
            "body_preview": r["body_preview"],
        }
        for r in results if r["phish_prob"] < 0.25
    ]

    # Sort by phish_prob descending (closest to boundary first)
    missed_025.sort(key=lambda x: x["phish_prob"], reverse=True)

    # --- Detect generation model ---
    models = list({r["generation_model"] for r in results})
    generation_model = models[0] if len(models) == 1 else ", ".join(sorted(models))

    # --- Build output ---
    detection_rate_025 = by_tau["at_tau_0.25"]["detection_rate"]
    delta = round(detection_rate_025 - corpus_recall_025, 4)

    output = {
        "synthetic_phishing_evaluation": {
            "total_samples": len(results),
            "generation_model": generation_model,
            **by_tau,
        },
        "by_intent_category": by_intent_tau,
        "missed_emails_at_tau_0.25": missed_025,
        "comparison_to_corpus": {
            "corpus_recall_at_tau_0.25": corpus_recall_025,
            "synthetic_detection_rate_at_tau_0.25": detection_rate_025,
            "delta": delta,
            "interpretation": interpret_delta(detection_rate_025, corpus_recall_025),
        },
    }

    # --- Save ---
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    # --- Print summary ---
    print(f"\n--- Adversarial Evaluation Results ---")
    print(f"Total synthetic emails: {len(results)}")
    print(f"Generation model: {generation_model}")
    print()
    for tau in THRESHOLDS:
        tau_key = TAU_KEYS[tau]
        t = by_tau[tau_key]
        print(f"τ={tau}:")
        print(f"  Detected:       {t['detected']}/{len(results)} "
              f"({t['detection_rate']*100:.1f}%)")
        print(f"  Missed (evaded):{t['missed']}/{len(results)} "
              f"({t['attack_success_rate']*100:.1f}%)")

    print(f"\nCorpus recall @τ=0.25:        {corpus_recall_025:.4f}")
    print(f"Synthetic detection @τ=0.25:  {detection_rate_025:.4f}")
    print(f"Delta:                         {delta:+.4f}")
    print(f"\nInterpretation: {output['comparison_to_corpus']['interpretation']}")
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
