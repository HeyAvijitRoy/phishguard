#!/usr/bin/env python3
"""Train a binary phish vs ham classifier on the FULL dataset.
Inputs:
- ml/data_processed/email_corpus.jsonl
Outputs:
- ml/export/phish_binary_hf/ (model + tokenizer)
- ml/export/phish_binary_hf/labels.json
"""

import argparse
import json
import os
import random
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from datasets import Dataset, Features, Value
from sklearn.metrics import f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

LABELS = ["ham", "phish"]


def load_jsonl(path: str) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def build_dataset(rows: List[Dict]) -> Dataset:
    texts = [f"{r.get('subject', '')}\n{r.get('body', '')}".strip() for r in rows]
    labels = [int(r.get("label_phish", 0)) for r in rows]
    features = Features({"text": Value("string"), "labels": Value("int64")})
    return Dataset.from_dict({"text": texts, "labels": labels}, features=features)


def tokenize_function(tokenizer, max_length: int):
    def _tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
            padding="max_length",
        )

    return _tokenize


def stratified_split(rows: List[Dict], seed: int, val_ratio: float) -> Tuple[List[Dict], List[Dict]]:
    rng = random.Random(seed)
    phish = [r for r in rows if int(r.get("label_phish", 0)) == 1]
    ham = [r for r in rows if int(r.get("label_phish", 0)) == 0]

    rng.shuffle(phish)
    rng.shuffle(ham)

    def split_group(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        n_val = max(1, int(len(items) * val_ratio)) if items else 0
        return items[n_val:], items[:n_val]

    train_phish, val_phish = split_group(phish)
    train_ham, val_ham = split_group(ham)

    train = train_phish + train_ham
    val = val_phish + val_ham

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    f1 = f1_score(labels, preds, average="binary", zero_division=0)
    return {"f1": f1}


class EpochLogCallback(TrainerCallback):
    """Print epoch, train loss, eval loss, eval F1 after each epoch."""

    def on_epoch_end(self, args, state, control, **kwargs):
        epoch = round(state.epoch)
        train_loss = next(
            (e["loss"] for e in reversed(state.log_history)
             if "loss" in e and "eval_loss" not in e),
            "N/A",
        )
        eval_entry = next(
            (e for e in reversed(state.log_history) if "eval_loss" in e),
            {},
        )
        eval_loss = eval_entry.get("eval_loss", "N/A")
        eval_f1 = eval_entry.get("eval_f1", "N/A")
        print(
            f"\n[Epoch {epoch}] train_loss={train_loss}  "
            f"eval_loss={eval_loss}  eval_f1={eval_f1}"
        )


def main(args: argparse.Namespace) -> None:
    rows = load_jsonl(args.corpus_path)
    train_rows, val_rows = stratified_split(rows, args.seed, args.val_ratio)

    print(f"Full dataset — train: {len(train_rows)}, val: {len(val_rows)}")

    train_ds = build_dataset(train_rows)
    val_ds = build_dataset(val_rows)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    train_ds = train_ds.map(tokenize_function(tokenizer, args.max_length), batched=True)
    val_ds = val_ds.map(tokenize_function(tokenizer, args.max_length), batched=True)

    train_ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
    val_ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])

    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=2,
        problem_type="single_label_classification",
    )

    use_fp16 = args.fp16 or torch.cuda.is_available()

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        warmup_ratio=args.warmup_ratio,
        num_train_epochs=args.epochs,
        fp16=use_fp16,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=100,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=[EpochLogCallback()],
    )

    trainer.train()

    export_dir = args.export_dir
    os.makedirs(export_dir, exist_ok=True)
    trainer.save_model(export_dir)
    tokenizer.save_pretrained(export_dir)

    labels_path = os.path.join(export_dir, "labels.json")
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(LABELS, f, indent=2, ensure_ascii=True)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    ml_root = project_root / "ml"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus-path",
        default=str(ml_root / "data_processed" / "email_corpus.jsonl"),
    )
    parser.add_argument("--base-model", default="distilbert-base-uncased")
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--fp16", action="store_true", default=False)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument(
        "--output-dir",
        default=str(ml_root / "runs" / "phish_binary"),
    )
    parser.add_argument(
        "--export-dir",
        default=str(ml_root / "export" / "phish_binary_hf"),
    )
    main(parser.parse_args())
