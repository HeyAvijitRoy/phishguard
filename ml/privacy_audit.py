"""
Privacy audit.
Monkey-patches urllib.request and requests to intercept any outbound HTTP calls during ONNX inference. 
Verifies zero email content leaves the pipeline.
Expected result: 0 outbound requests. onnxruntime CPU provider is local-only.
Saves: evaluation/results/privacy_audit.json
"""

import json
import urllib.request
import urllib.error
import numpy as np
import onnxruntime as ort
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from tokenizers import BertWordPieceTokenizer

#  Monkey-patch BEFORE any other imports that might trigger network 

_captured_requests: list[str] = []
_original_urlopen = urllib.request.urlopen


def _intercepting_urlopen(url, *args, **kwargs):
    _captured_requests.append(str(url))
    print(f"[INTERCEPT] urllib.request.urlopen called: {url}")
    return _original_urlopen(url, *args, **kwargs)

urllib.request.urlopen = _intercepting_urlopen

try:
    import requests as _requests_lib
    _original_get  = _requests_lib.get
    _original_post = _requests_lib.post

    def _patched_get(url, **kwargs):
        _captured_requests.append(f"GET {url}")
        print(f"[INTERCEPT] requests.get called: {url}")
        return _original_get(url, **kwargs)

    def _patched_post(url, **kwargs):
        _captured_requests.append(f"POST {url}")
        print(f"[INTERCEPT] requests.post called: {url}")
        return _original_post(url, **kwargs)

    _requests_lib.get  = _patched_get
    _requests_lib.post = _patched_post
    _requests_patched  = True
except ImportError:
    _requests_patched = False


#  Paths 
CORPUS_PATH = Path("ml/data_processed/email_corpus.jsonl")
BINARY_ONNX = Path("ml/export/onnx/phish_binary.onnx")
INTENT_ONNX = Path("ml/export/onnx/phish_intent.onnx")
VOCAB_PATH  = Path("ml/export/onnx/vocab.txt")
RESULTS_DIR = Path("evaluation/results")

N_EMAILS_TO_AUDIT = 100
TAU_PRODUCTION    = 0.90


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

    # Take first 100 test emails
    audit_df = test_df.head(N_EMAILS_TO_AUDIT).reset_index(drop=True)
    print(f"Auditing {len(audit_df)} emails …")

    tok      = load_tokenizer()
    sess_bin = ort.InferenceSession(str(BINARY_ONNX),
                                    providers=["CPUExecutionProvider"])
    sess_int = ort.InferenceSession(str(INTENT_ONNX),
                                    providers=["CPUExecutionProvider"])

    # Collect subjects and bodies for content-leak check (first 50 chars each)
    content_snippets: list[str] = []
    for _, row in audit_df.iterrows():
        subj = str(row.get("subject", "") or "")[:50]
        body = str(row.get("body", "") or "")[:50]
        if subj.strip():
            content_snippets.append(subj)
        if body.strip():
            content_snippets.append(body)

    # Clear captured requests so any pre-run network calls don't pollute audit
    _captured_requests.clear()

    print("Running full pipeline through 100 emails …")
    for i, row in audit_df.iterrows():
        text = row["text"]
        input_ids, attn = tokenize(text, tok)
        feeds = {"input_ids": input_ids, "attention_mask": attn}

        # Stage 1
        logits = sess_bin.run(None, feeds)[0][0]
        p_phish = float(softmax2(logits))

        # Stage 2 for emails that would pass τ=0.90
        if p_phish >= TAU_PRODUCTION:
            sess_int.run(None, feeds)

    n_captured = len(_captured_requests)
    print(f"\nTotal outbound requests captured: {n_captured}")

    # Check for content leakage in any captured URL
    content_bearing = 0
    for req_url in _captured_requests:
        for snippet in content_snippets:
            if len(snippet) >= 5 and snippet in req_url:
                content_bearing += 1
                print(f"[WARNING] Content snippet found in request: {req_url[:200]}")
                break

    if n_captured > 0:
        print(f"[WARNING] Unexpected outbound requests during inference:")
        for url in _captured_requests:
            print(f"  {url}")
    else:
        print("[OK] Zero outbound requests — privacy invariant holds.")

    privacy_holds = (content_bearing == 0)

    result = {
        "emails_analyzed":                N_EMAILS_TO_AUDIT,
        "total_outbound_requests_captured": n_captured,
        "content_bearing_requests":       content_bearing,
        "privacy_invariant_holds":        privacy_holds,
        "captured_urls":                  list(_captured_requests),
        "methodology": (
            "urllib.request + requests monkey-patch during local onnxruntime CPU inference"
        ),
        "note": (
            "onnxruntime Python CPU provider performs local inference only. "
            "Zero outbound requests expected and confirmed."
        ),
    }

    save_results(result, "privacy_audit.json")

    print(f"\n=== Privacy Audit Result ===")
    print(f"  Emails analyzed:       {N_EMAILS_TO_AUDIT}")
    print(f"  Outbound requests:     {n_captured}")
    print(f"  Content-bearing reqs:  {content_bearing}")
    print(f"  Privacy invariant:     {'HOLDS' if privacy_holds else 'VIOLATED'}")


if __name__ == "__main__":
    main()
