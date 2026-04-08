#!/usr/bin/env python3
"""Sweep thresholds for intent-based semantic suspicion on validation set.

Output:
- reports/thresholds.json
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer


def load_jsonl(path: str) -> List[Dict]:
    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_session(model_path: str) -> ort.InferenceSession:
    providers = ["CPUExecutionProvider"]
    return ort.InferenceSession(model_path, providers=providers)


def infer_probs(
    session: ort.InferenceSession,
    tokenizer: AutoTokenizer,
    texts: List[str],
    max_length: int,
) -> np.ndarray:
    inputs = tokenizer(
        texts,
        return_tensors="np",
        truncation=True,
        max_length=max_length,
        padding="max_length",
    )

    feed = {}
    for inp in session.get_inputs():
        name = inp.name
        if name in inputs:
            arr = inputs[name]
            if arr.dtype != np.int64:
                arr = arr.astype(np.int64)
            feed[name] = arr

    outputs = session.run(None, feed)
    logits = outputs[0]
    return sigmoid(logits)


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, int]:
    tp = int(np.sum(np.logical_and(y_true, y_pred)))
    fp = int(np.sum(np.logical_and(~y_true, y_pred)))
    tn = int(np.sum(np.logical_and(~y_true, ~y_pred)))
    fn = int(np.sum(np.logical_and(y_true, ~y_pred)))
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def metrics_from_confusion(conf: Dict[str, int]) -> Dict[str, float]:
    tp = conf["tp"]
    fp = conf["fp"]
    tn = conf["tn"]
    fn = conf["fn"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"precision": precision, "recall": recall, "fpr": fpr}


def pick_threshold(sweep: List[Dict], target_fpr: float) -> Dict:
    eligible = [row for row in sweep if row["fpr"] <= target_fpr]
    if not eligible:
        return sweep[-1]
    return max(eligible, key=lambda r: r["recall"])


def main(args: argparse.Namespace) -> None:
    rows = load_jsonl(args.val_path)
    texts = [f"{r.get('subject', '')}\n{r.get('body', '')}".strip() for r in rows]

    tokenizer = AutoTokenizer.from_pretrained(args.onnx_dir)
    session = build_session(os.path.join(args.onnx_dir, "phish_intent.onnx"))

    all_probs: List[np.ndarray] = []
    for batch in chunked(texts, args.batch_size):
        probs = infer_probs(session, tokenizer, batch, args.max_length)
        all_probs.append(probs)

    probs_all = np.vstack(all_probs)
    semantic = np.max(probs_all, axis=1)
    y_true = np.array([float(r.get("label_phish", 0)) for r in rows]) > 0.5

    thresholds = [round(t, 2) for t in np.arange(args.min_t, args.max_t + 1e-9, args.step)]
    sweep: List[Dict] = []
    for t in thresholds:
        y_pred = semantic >= t
        conf = confusion_counts(y_true, y_pred)
        stats = metrics_from_confusion(conf)
        sweep.append({"threshold": t, **conf, **stats})

    picked = {
        "target_fpr_0_01": pick_threshold(sweep, 0.01),
        "target_fpr_0_03": pick_threshold(sweep, 0.03),
    }

    output = {
        "model": "phish_intent.onnx",
        "metric_basis": "semanticSuspicion=max(intent_probs)",
        "sweep": sweep,
        "picked": picked,
    }

    os.makedirs(args.reports_dir, exist_ok=True)
    out_path = os.path.join(args.reports_dir, "thresholds.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=True)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    ml_root = project_root / "ml"

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--val-path",
        default=str(ml_root / "data_processed" / "val_intent.jsonl"),
    )
    parser.add_argument(
        "--onnx-dir",
        default=str(ml_root / "export" / "onnx"),
    )
    parser.add_argument(
        "--reports-dir",
        default=str(project_root / "reports"),
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--min-t", type=float, default=0.05)
    parser.add_argument("--max-t", type=float, default=0.95)
    parser.add_argument("--step", type=float, default=0.05)
    main(parser.parse_args())
