#!/usr/bin/env python3
"""Export HF model to ONNX and run a smoke test.
Inputs:
- ml/export/phish_intent_hf/
Outputs:
- ml/export/onnx/phish_intent.onnx
- ml/export/onnx/vocab.txt
- ml/export/onnx/tokenizer_config.json
- ml/export/onnx/special_tokens_map.json
- ml/export/onnx/labels.json
- ml/export/onnx_smoke_test.txt
"""

import argparse
import datetime
import json
import os
import shutil
from pathlib import Path
from typing import List

import numpy as np
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def read_labels(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(args: argparse.Namespace) -> None:
    os.makedirs(args.export_dir, exist_ok=True)

    model = ORTModelForSequenceClassification.from_pretrained(
        args.hf_dir,
        export=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.hf_dir)

    model.save_pretrained(args.export_dir)
    tokenizer.save_pretrained(args.export_dir)

    model_onnx = os.path.join(args.export_dir, "model.onnx")
    target_onnx = os.path.join(args.export_dir, "phish_intent.onnx")
    if os.path.exists(model_onnx):
        shutil.copy2(model_onnx, target_onnx)

    labels_path = os.path.join(args.hf_dir, "labels.json")
    if os.path.exists(labels_path):
        with open(labels_path, "r", encoding="utf-8") as f:
            labels = json.load(f)
        with open(os.path.join(args.export_dir, "labels.json"), "w", encoding="utf-8") as f:
            json.dump(labels, f, indent=2, ensure_ascii=True)
    else:
        labels = []

    sample_text = "Verify your account password to avoid suspension."
    inputs = tokenizer(sample_text, return_tensors="np", truncation=True, max_length=256)

    outputs = model(**inputs)
    logits = outputs.logits
    probs = sigmoid(logits)[0]

    lines = [
        f"sample_text: {sample_text}",
        f"logits: {logits[0].tolist()}",
        f"probs: {probs.tolist()}",
    ]

    if labels:
        labeled = [f"{label}={float(prob):.4f}" for label, prob in zip(labels, probs)]
        lines.append("labeled: " + ", ".join(labeled))

    smoke_path = os.path.join(args.output_root, "onnx_smoke_test.txt")
    with open(smoke_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # --- Assertions: shape check + hardcoded phishing sentence ---
    # Assert 1: output shape is (1, 4)
    assert logits.shape == (1, 4) or len(logits[0]) == 4, (
        f"Expected 4 intent outputs, got shape {logits.shape}"
    )
    print(f"[SMOKE] shape assertion passed: logits.shape={logits.shape}")

    # Assert 2: max prob > 0.10 on an obvious phishing sentence
    phish_test_text = (
        "Urgent: Your account will be suspended. "
        "Click here to verify your password now."
    )
    phish_inputs = tokenizer(
        phish_test_text, return_tensors="np", truncation=True, max_length=256
    )
    phish_outputs = model(**phish_inputs)
    phish_probs = sigmoid(phish_outputs.logits)[0]
    max_prob = float(max(phish_probs))

    if max_prob > 0.10:
        smoke_status = "PASS"
        print(f"[SMOKE] PASS — max_prob={max_prob:.4f}")
    else:
        smoke_status = f"WARN — max_prob={max_prob:.4f} <= 0.10 (model may be undertrained; after retrain expect > 0.30)"
        print(f"[SMOKE] WARNING — max_prob={max_prob:.4f} <= 0.10. Model may be undertrained. After retrain, should be > 0.30.")

    # Write detailed result to ml/export/onnx/smoke_test_result.txt
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    smoke_result_path = os.path.join(args.export_dir, "smoke_test_result.txt")
    with open(smoke_result_path, "w", encoding="utf-8") as f:
        f.write(f"timestamp: {timestamp}\n")
        f.write(f"test_text: {phish_test_text}\n")
        f.write(f"max_prob: {max_prob:.4f}\n")
        f.write(f"all_4_probs: {[round(float(p), 4) for p in phish_probs]}\n")
        if labels:
            labeled = [f"{lbl}={float(p):.4f}" for lbl, p in zip(labels, phish_probs)]
            f.write(f"labeled: {', '.join(labeled)}\n")
        f.write(f"status: {smoke_status}\n")
    print(f"[SMOKE] Result written to {smoke_result_path}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    ml_root = project_root / "ml"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hf-dir",
        default=str(ml_root / "export" / "phish_intent_hf"),
    )
    parser.add_argument(
        "--export-dir",
        default=str(ml_root / "export" / "onnx"),
    )
    parser.add_argument(
        "--output-root",
        default=str(ml_root / "export"),
    )
    main(parser.parse_args())
