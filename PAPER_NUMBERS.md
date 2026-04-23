# PhishGuard — Canonical Paper Numbers

Every metric cited in the paper is listed here with its source file in
`evaluation/results/`. This file can be used as an index when spot-checking any
reported number.

All values are fixed at submission time

Last updated: 2026-03-22

---

## Dataset

| Field | Value | Source |
|-------|-------|--------|
| Total corpus | 33,105 emails | `ml/data_processed/stats.json` |
| Phishing | 7,781 (23.5%) | `ml/data_processed/stats.json` |
| Benign | 25,324 (76.5%) | `ml/data_processed/stats.json` |
| Data source | Zenodo Phishing Email Curated Datasets | `ml/build_dataset.py` |
| Enron ham included | No (`enron_count=0`) | `ml/data_processed/stats.json` |
| Train/test split | 80/20 stratified, `random_state=42` | `ml/eval_binary_v2.py` |
| Training set size | 26,484 | split from full corpus |
| Test set size | 6,621 | `evaluation/results/binary_eval_v2.json` |
| Test phishing | 1,556 | `evaluation/results/binary_eval_v2.json` |
| Test benign | 5,065 | `evaluation/results/binary_eval_v2.json` |
| Intent label method | Keyword-derived weak labels | `ml/build_dataset.py:weak_label_intents` |
| Ham intent labels | All-zero by construction | see `ml/build_dataset.py` |
| Exact duplicates removed | 6,182 | `ml/build_dataset.py`, `ml/data_processed/stats.json` |
| Post-dedup corpus size | 33,105 | `ml/data_processed/stats.json` |

---

## Binary Classifier Performance

### Primary operating point — τ = 0.25 (research / evaluation)

| Metric | Value | Source |
|--------|-------|--------|
| Precision | 0.9866 | `evaluation/results/binary_eval_v2.json` |
| Recall | 0.9916 | `evaluation/results/binary_eval_v2.json` |
| F1 | 0.9891 | `evaluation/results/binary_eval_v2.json` |
| FPR | 0.41% | `evaluation/results/binary_eval_v2.json` |
| True positives | 1,543 | `evaluation/results/binary_eval_v2.json` |
| False positives | 21 | `evaluation/results/binary_eval_v2.json` |
| True negatives | 5,044 | `evaluation/results/binary_eval_v2.json` |
| False negatives | 13 | `evaluation/results/binary_eval_v2.json` |

### Production operating point — τ = 0.90 (deployed gate in `Taskpane.tsx`)

| Metric | Value | Source |
|--------|-------|--------|
| Precision | 0.9916 | `evaluation/results/binary_eval_v2.json` |
| Recall | 0.9807 | `evaluation/results/binary_eval_v2.json` |
| F1 | 0.9861 | `evaluation/results/binary_eval_v2.json` |
| FPR | 0.26% | `evaluation/results/binary_eval_v2.json` |

### Discrimination metrics (full threshold sweep)

| Metric | Value | Source |
|--------|-------|--------|
| ROC-AUC | 0.9995 | `evaluation/results/threshold_sensitivity.json` |
| PR-AUC | 0.9983 | `evaluation/results/threshold_sensitivity.json` |

### 5-fold stratified cross-validation (full 33,105-email corpus, τ = 0.25)

| Metric | Mean | Std | Source |
|--------|------|-----|--------|
| Precision | 0.9882 | ±0.0025 | `evaluation/results/crossval.json` |
| Recall | 0.9910 | ±0.0028 | `evaluation/results/crossval.json` |
| F1 | 0.9896 | ±0.0022 | `evaluation/results/crossval.json` |
| FPR | 0.36% | ±0.08% | `evaluation/results/crossval.json` |

---

## Baseline Comparison (τ = 0.25, same 6,621-email test set)

| System | Precision | Recall | F1 | FPR | Stage 1 Latency |
|--------|-----------|--------|----|-----|-----------------|
| TF-IDF + Logistic Regression | 0.9805 | 0.9049 | 0.9412 | 0.55% | 0.046 ms |
| TF-IDF + SVM (LinearSVC) | 0.9866 | 0.9467 | 0.9662 | 0.39% | 0.042 ms |
| ONNX non-staged (no gate) | 0.9866 | 0.9916 | 0.9891 | 0.41% | 44.8 ms |
| PhishGuard staged (τ = 0.25) | **0.9866** | **0.9916** | **0.9891** | **0.41%** | **40.7 ms** |

Key finding: staged execution costs zero accuracy versus the non-staged ONNX
baseline while eliminating Stage 2 for 76.4% of the corpus.

Source: `evaluation/results/baselines.json`

---

## Intent Model Performance (phishing test set only, τ_intent = 0.50)

| Label | Precision | Recall | F1 | Support |
|-------|-----------|--------|----|---------|
| credential_harvesting | 0.5333 | 0.2857 | 0.3721 | 28 |
| payment_fraud | 0.9550 | 0.8724 | 0.9118 | 243 |
| threat_language | 0.6000 | 0.1364 | 0.2222 | 22 |
| impersonation | 1.0000 | 0.3182 | 0.4828 | 22 |
| **Micro average** | — | — | **0.8156** | 315 |
| **Macro average** | — | — | **0.4972** | — |

Ham FPR per label: effectively 0% (max observed: 0.0197% for payment_fraud).

Note: Low macro F1 reflects class imbalance and the weak-label methodology.
Payment fraud dominates the support (243/315 = 77%). Micro F1 = 0.8156 reflects
overall performance weighted by support.

Source: `evaluation/results/intent_labels_eval.json`

---

## Staged Compute Efficiency

| Threshold | Stage 2 Trigger Rate | Compute Savings |
|-----------|----------------------|-----------------|
| τ = 0.05 | 23.77% | 76.23% |
| τ = 0.25 (research) | 23.62% | 76.38% |
| τ = 0.50 | 23.49% | 76.51% |
| τ = 0.90 (production) | 23.24% | 76.76% |
| τ = 0.95 | 22.99% | 77.01% |

Savings are stable across all thresholds (76.2–77.0%) because the binary model
produces a bimodal confidence distribution: clearly benign emails cluster near
p_phish ≈ 0 and clearly phishing emails cluster near p_phish ≈ 1. The fraction
of emails in the marginal zone is small regardless of threshold placement.

Source: `evaluation/results/staged_efficiency.json`

---

## Runtime Latency

Measurement methodology: Python `onnxruntime` CPU provider, `session.run()` timed
exclusively, 3 warmup passes before timing begins, tokenization excluded.
Hardware: CPU (matches WASM single-threaded deployment context).

| Stage | Emails | Mean | P95 |
|-------|--------|------|-----|
| Stage 1 (all 6,621 test emails) | 6,621 | 40.7 ms | 45.8 ms |
| Stage 2 at τ = 0.90 (gate-passed only) | 1,539 | 41.6 ms | — |
| Combined pipeline at τ = 0.90 | — | 82.2 ms | 89.7 ms |

The full pipeline stays below 100 ms at P95 under single-threaded WASM constraints.

Source: `evaluation/results/full_pipeline_latency.json`, `evaluation/results/stage1_latency.csv`,
`evaluation/results/stage2_latency_tau090.csv`

---

## Browser-Side Wall-Clock Latency (Deployed Add-in)

Measurement methodology: browser-side wall-clock instrumentation and
deployment console logs from the hosted Outlook add-in taskpane in
non-pinned hosting. The Office.js taskpane lifecycle resets module
state on each email selection, so deployment latency reflects first-load
asset fetch, runtime/session setup, and conditional Stage 2 execution.

| Regime | Observed latency |
|--------|------------------|
| Initial first-load event | > 6 s |
| Repeated Stage 1-only analyses | ~2.0 s |
| Repeated Stage 2-triggered analyses (Full Pipeline) | ~3.3 s |

Source: deployed taskpane console logs, including `[PhishGuard Latency]`
entries and tokenization/runtime verification logs.

Note: Subsequent analyses benefit from browser-cached model assets, but
wall-clock latency remains dominated by taskpane/runtime overhead and
session lifecycle behavior rather than isolated inference computation.
Admin-enforced pinning is intended to recover warm-path behavior in
enterprise deployment.

---

## Privacy Audit

| Metric | Result |
|--------|--------|
| Emails analyzed | 100 |
| Outbound HTTP requests captured | 0 |
| Content-bearing requests | 0 |
| Privacy invariant | HOLDS |

Methodology: `urllib.request.urlopen` and `requests.get`/`post` monkey-patched
before any model imports; all outbound HTTP calls and payload contents recorded.

Source: `evaluation/results/privacy_audit.json`

---

## Browser-Path Privacy Audit (Canary Scan)

| Metric | Result |
|--------|--------|
| mitmproxy flows inspected | 653 |
| Canary tests run | 15 |
| Canary matches found | 0 |
| Verdict | PASS |

Canaries included: synthetic high-entropy markers
(PHISHGUARD_CANARY_SUBJECT_7F3A91, PHISHGUARD_CANARY_BODY_29C8D4)
and natural subject/body fragments from audited emails spanning
benign and phishing categories.

Source: `evaluation/privacy_audit_canary_report.jsonl`

## Adversarial Evaluation (LLM-Generated Phishing, τ = 0.25)

| Category | n | Detected | Missed | Detection Rate |
|----------|---|----------|--------|----------------|
| threat_language | 50 | 50 | 0 | 100.0% |
| payment_fraud | 50 | 46 | 4 | 92.0% |
| credential_harvesting | 50 | 44 | 6 | 88.0% |
| impersonation (BEC) | 50 | 25 | 25 | 50.0% |
| **Overall** | **200** | **165** | **35** | **82.5%** |

Corpus phishing recall at τ = 0.25: 99.16%
Synthetic detection at τ = 0.25: 82.5%
Gap: −16.7 percentage points

The evasion gap is concentrated in impersonation (50% detection). BEC-style emails
that read as ordinary internal communications contain no content-level phishing
signals; the binary classifier cannot distinguish them from legitimate email.
This motivates the auth.ts and thread.ts signal components, which provide
identity-level evidence independent of message content.

Source: `evaluation/results/adversarial_eval.json`

---

## System Architecture Constants

| Constant | Value | Source location |
|----------|-------|-----------------|
| Binary gate threshold (production) | τ = 0.90 | `addin/src/taskpane/Taskpane.tsx` line 42 |
| Binary gate threshold (research/eval) | τ = 0.25 | `ml/eval_binary_v2.py` |
| Max input characters | 8,000 | `addin/src/taskpane/logic/binary.ts` |
| Max token sequence length | 256 | `addin/src/taskpane/logic/binary.ts` |
| Fusion weight α (S_bin) | 0.50 | `addin/src/taskpane/logic/fuse.ts` `FUSION_WEIGHTS` |
| Fusion weight β (S_int) | 0.30 | `addin/src/taskpane/logic/fuse.ts` `FUSION_WEIGHTS` |
| Fusion weight γ (S_struct) | 0.15 | `addin/src/taskpane/logic/fuse.ts` `FUSION_WEIGHTS` |
| Fusion weight δ (S_meta) | 0.05 | `addin/src/taskpane/logic/fuse.ts` `FUSION_WEIGHTS` |
| S_struct normalization ceiling | 100 | `addin/src/taskpane/logic/fuse.ts` `MAX_STRUCT_SCORE` |
| S_meta normalization ceiling | 52 | `addin/src/taskpane/logic/fuse.ts` `MAX_META_SCORE` |
| S_final tier: Medium | ≥ 0.40 | `addin/src/taskpane/logic/fuse.ts` `TIER_THRESHOLDS` |
| S_final tier: High | ≥ 0.70 | `addin/src/taskpane/logic/fuse.ts` `TIER_THRESHOLDS` |
| score.ts tier: Medium | score ≥ 25, strongEvidence ≥ 1 | `addin/src/taskpane/logic/score.ts` |
| score.ts tier: High | score ≥ 70, strongEvidence ≥ 2 | `addin/src/taskpane/logic/score.ts` |
| Short-text dampening threshold | 220 chars, factor 0.55 | `addin/src/taskpane/logic/score.ts` |
| Very short dampening threshold | 90 chars, factor 0.35 | `addin/src/taskpane/logic/score.ts` |
| Hard override threshold | p_phish ≥ 0.995 | `addin/src/taskpane/logic/score.ts` |
| ONNX runtime | onnxruntime-web (WASM) | `binary.ts`, `nlp.ts` |
| Tensor dtype | int64 (BigInt64Array) | `binary.ts` lines 122–123 |
| Intent activation | sigmoid per logit (multi-label) | `nlp.ts` line 188 |
| Binary activation | softmax (2-class) | `binary.ts` lines 146–153 |
| Session caching | Singleton per model | `binary.ts`, `nlp.ts` module-level |
| WASM threading | Single-threaded | `Taskpane.tsx` `ort.env` config |

---

## Model Artifacts

| Artifact | Size | SHA-256 |
|----------|------|---------|
| `phish_binary.onnx` | 267,932,171 bytes | `e0b8970aa11ea7cbed718d8c0e01fa8851d1bb97bdbf73c2223d7ddcfb5b38cf` |
| `phish_intent.onnx` | 267,938,323 bytes | `260ae858c5c5067954ba402fded0d32efdfc845a8cfb1821ca053de5857c1f0c` |

Source: `ml/export/onnx/manifest.json`

Base model: `distilbert-base-uncased`
Architecture: 6 Transformer layers, 12 attention heads, 768-dimensional hidden
state, 30,522-token WordPiece vocabulary
Training: 3 epochs, full 33,105-email corpus (26,484 training / 6,621 test),
stratified 80/20 split, `random_state=42`
Hardware used for training: RTX 3080 Ti Laptop GPU