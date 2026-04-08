#!/usr/bin/env python3
"""Build normalized dataset and weak intent labels.

Outputs:
- ml/data_processed/email_corpus.jsonl
- ml/data_processed/stats.json
- ml/data_processed/train_intent.jsonl
- ml/data_processed/val_intent.jsonl
"""

import argparse
import csv
import hashlib
import html
import json
import os
import random
import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from typing import Dict, Iterable, List, Optional, Tuple
from pathlib import Path


MAX_BODY_CHARS = 8000
MIN_BODY_CHARS = 50


@dataclass
class Record:
    id: str
    source: str
    label_phish: int
    subject: str
    body: str
    raw_path: str
    sender: Optional[str] = None
    links: Optional[List[str]] = None
    timestamp: Optional[str] = None

    def to_json(self) -> Dict:
        obj = {
            "id": self.id,
            "source": self.source,
            "label_phish": self.label_phish,
            "subject": self.subject,
            "body": self.body,
            "raw_path": self.raw_path,
        }
        if self.sender:
            obj["from"] = self.sender
        if self.links:
            obj["links"] = self.links
        if self.timestamp:
            obj["timestamp"] = self.timestamp
        return obj


def normalize_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def cap_body(text: str) -> str:
    if len(text) <= MAX_BODY_CHARS:
        return text
    return text[:MAX_BODY_CHARS]


def sha_id(subject: str, body: str) -> str:
    base = f"{subject}\n{body[:2000]}"
    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()


def html_to_text(raw: str) -> str:
    # Very lightweight HTML stripping.
    no_tags = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(no_tags)


def extract_body_from_message(msg) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in content_disp:
                continue
            if content_type == "text/plain":
                try:
                    parts.append(part.get_content())
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    parts.append(payload.decode(errors="replace"))
        if parts:
            return "\n".join(parts)
        # Fallback to HTML if no plain text parts
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    return html_to_text(part.get_content())
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    return html_to_text(payload.decode(errors="replace"))
        return ""

    # Not multipart
    content_type = msg.get_content_type()
    try:
        payload = msg.get_content()
    except Exception:
        raw = msg.get_payload(decode=True) or b""
        payload = raw.decode(errors="replace")

    if content_type == "text/html":
        return html_to_text(payload)
    return payload


def iter_enron_records(root_dir: str) -> Iterable[Record]:
    parser = BytesParser(policy=policy.default)

    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            file_path = os.path.join(dirpath, name)
            try:
                with open(file_path, "rb") as f:
                    msg = parser.parse(f)
            except Exception:
                continue

            subject = normalize_text(str(msg.get("subject", "")))
            sender = normalize_text(str(msg.get("from", "")))
            date = normalize_text(str(msg.get("date", "")))
            body_raw = extract_body_from_message(msg)
            body = normalize_text(body_raw)
            body = cap_body(body)

            if len(body) < MIN_BODY_CHARS:
                continue

            record_id = sha_id(subject, body)
            yield Record(
                id=record_id,
                source="enron",
                label_phish=0,
                subject=subject,
                body=body,
                raw_path=file_path,
                sender=sender or None,
                timestamp=date or None,
            )


def sniff_dialect(sample: str) -> csv.Dialect:
    sniffer = csv.Sniffer()
    return sniffer.sniff(sample)


def detect_columns(headers: List[str]) -> Dict[str, Optional[str]]:
    lower = [h.strip().lower() for h in headers]

    def pick(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            for idx, name in enumerate(lower):
                if c in name:
                    return headers[idx]
        return None

    return {
        "subject": pick(["subject", "subj"]),
        "body": pick(["body", "content", "text", "message", "email"]),
        "label": pick(["label", "class", "phish", "spam", "is_phish"]),
        "sender": pick(["sender", "from"]),
        "links": pick(["url", "urls", "links"]),
        "timestamp": pick(["date", "time", "timestamp"]),
    }


def parse_label(value: str) -> int:
    v = (value or "").strip().lower()
    if v == "":
        return 0
    if v.isdigit():
        return 1 if int(v) != 0 else 0
    if "phish" in v or "spam" in v or "fraud" in v or "malicious" in v:
        return 1
    return 0


def parse_links(value: str) -> List[str]:
    if not value:
        return []
    chunks = re.split(r"[\s,;]+", value.strip())
    return [c for c in chunks if c]


def iter_zenodo_records(root_dir: str) -> Iterable[Record]:
    for name in os.listdir(root_dir):
        if not name.lower().endswith(".csv"):
            continue
        if name.lower().endswith("_vectorized_data.csv"):
            continue

        file_path = os.path.join(root_dir, name)
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                sample = f.read(4096)
                f.seek(0)
                dialect = sniff_dialect(sample)
                reader = csv.DictReader(f, dialect=dialect)

                if not reader.fieldnames:
                    continue

                col_map = detect_columns(reader.fieldnames)
                for idx, row in enumerate(reader):
                    subject = normalize_text(row.get(col_map["subject"], "") if col_map["subject"] else "")
                    body = normalize_text(row.get(col_map["body"], "") if col_map["body"] else "")
                    sender = normalize_text(row.get(col_map["sender"], "") if col_map["sender"] else "")
                    timestamp = normalize_text(row.get(col_map["timestamp"], "") if col_map["timestamp"] else "")
                    links_raw = row.get(col_map["links"], "") if col_map["links"] else ""

                    body = cap_body(body)
                    if len(body) < MIN_BODY_CHARS:
                        continue

                    if col_map["label"]:
                        label_phish = parse_label(row.get(col_map["label"], ""))
                    else:
                        # Default to phishing-only when label column is missing.
                        label_phish = 1

                    record_id = sha_id(subject, body)
                    links = parse_links(links_raw)

                    yield Record(
                        id=record_id,
                        source="zenodo",
                        label_phish=label_phish,
                        subject=subject,
                        body=body,
                        raw_path=f"{file_path}#{idx}",
                        sender=sender or None,
                        links=links or None,
                        timestamp=timestamp or None,
                    )
        except Exception:
            continue


def weak_label_intents(text: str) -> Dict[str, int]:
    text_l = text.lower()

    credential = ["password", "passcode", "mfa", "otp", "one-time", "verify", "login", "sign in"]
    payment = ["invoice", "wire", "bank", "gift card", "refund", "payment", "transfer"]
    threat = ["suspend", "locked", "terminated", "final notice", "disabled", "legal action"]
    impersonation = ["ceo", "it support", "helpdesk", "vendor", "microsoft security", "security team"]

    def hit(keywords: List[str]) -> int:
        return 1 if any(k in text_l for k in keywords) else 0

    return {
        "intent_credential": hit(credential),
        "intent_payment": hit(payment),
        "intent_threat": hit(threat),
        "intent_impersonation": hit(impersonation),
    }


def stratified_split(records: List[Record], seed: int, val_ratio: float) -> Tuple[List[Record], List[Record]]:
    rng = random.Random(seed)
    phish = [r for r in records if r.label_phish == 1]
    ham = [r for r in records if r.label_phish == 0]

    rng.shuffle(phish)
    rng.shuffle(ham)

    def split_group(items: List[Record]) -> Tuple[List[Record], List[Record]]:
        n_val = max(1, int(len(items) * val_ratio)) if items else 0
        return items[n_val:], items[:n_val]

    train_phish, val_phish = split_group(phish)
    train_ham, val_ham = split_group(ham)

    train = train_phish + train_ham
    val = val_phish + val_ham

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def write_jsonl(path: str, rows: Iterable[Dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def build(args: argparse.Namespace) -> None:
    records: List[Record] = []
    stats = {
        "enron_count": 0,
        "zenodo_count": 0,
        "duplicates_removed": 0,
    }
    seen = set()

    for rec in iter_enron_records(args.enron_dir):
        stats["enron_count"] += 1
        if rec.id in seen:
            stats["duplicates_removed"] += 1
            continue
        seen.add(rec.id)
        records.append(rec)

    for rec in iter_zenodo_records(args.zenodo_dir):
        stats["zenodo_count"] += 1
        if rec.id in seen:
            stats["duplicates_removed"] += 1
            continue
        seen.add(rec.id)
        records.append(rec)

    os.makedirs(args.output_dir, exist_ok=True)

    corpus_path = os.path.join(args.output_dir, "email_corpus.jsonl")
    write_jsonl(corpus_path, (r.to_json() for r in records))

    stats["total_records"] = len(records)
    stats_path = os.path.join(args.output_dir, "stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=True)

    train, val = stratified_split(records, args.seed, args.val_ratio)

    def intent_rows(items: List[Record]) -> Iterable[Dict]:
        for rec in items:
            intents = {
                "intent_credential": 0,
                "intent_payment": 0,
                "intent_threat": 0,
                "intent_impersonation": 0,
            }
            if rec.label_phish == 1:
                intents = weak_label_intents(f"{rec.subject}\n{rec.body}")

            yield {
                "id": rec.id,
                "source": rec.source,
                "label_phish": rec.label_phish,
                "subject": rec.subject,
                "body": rec.body,
                **intents,
            }

    train_path = os.path.join(args.output_dir, "train_intent.jsonl")
    val_path = os.path.join(args.output_dir, "val_intent.jsonl")
    write_jsonl(train_path, intent_rows(train))
    write_jsonl(val_path, intent_rows(val))


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    ml_root = project_root / "ml"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--enron-dir",
        default=str(ml_root / "data_raw" / "enron-ham"),
        help="Path to Enron ham directory.",
    )
    parser.add_argument(
        "--zenodo-dir",
        default=str(ml_root / "data_raw" / "zenodo"),
        help="Path to Zenodo CSV directory.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ml_root / "data_processed"),
        help="Output directory for JSONL files.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
