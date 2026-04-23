# PhishGuard — Artifact Bundle

**PhishGuard** is a privacy-preserving, staged dual-model phishing detection
system deployed as a Microsoft 365 Outlook add-in. All semantic analysis
executes locally via ONNX Runtime WebAssembly — no email content is
transmitted off-device at any point during analysis.

This bundle contains everything needed to run the add-in, inspect the
inference pipeline, reproduce the evaluation metrics, and re-generate the
paper figures.

---

## What this artifact supports

- **Run the Outlook add-in** and interact with the full TypeScript inference
  pipeline in a live email client
- **Verify the trained ONNX models** against the SHA-256 hashes in the
  model manifest
- **Reproduce all evaluation metrics** by re-running the Python evaluation
  scripts against the shipped processed corpus
- **Re-generate all paper figures** from the stored evaluation outputs
- **Inspect the evidence chain** linking every reported metric to a
  machine-readable source file in `evaluation/results/`

---

## Repository layout

```
phishguard/
├── LICENSE
├── README.md                       This file
├── PAPER_NUMBERS.md                Canonical metric index → evaluation/results/
│
├── addin/                          Outlook add-in (TypeScript + React)
│   ├── manifest.xml                Local default manifest (same local target)
│   ├── manifest.dev.xml            Local development sideload manifest
│   ├── manifest.production.xml     Hosted enterprise deployment manifest
│   ├── package.json
│   ├── tsconfig.json
│   ├── webpack.config.js
│   ├── assets/                     Add-in icons
│   ├── public/models/              ONNX models land here after sync step
│   └── src/
│       ├── shared/types.ts         Shared TypeScript types
│       └── taskpane/
│           ├── Taskpane.tsx        Main pipeline orchestrator
│           ├── Taskpane.html 
│           ├── styles/      
│           ├── components/         UI components
│           │   ├── RiskBanner.tsx
│           │   ├── ReasonsList.tsx
│           │   ├── ActionButtons.tsx
│           │   ├── Controls.tsx
│           │   └── LinkInspector.tsx
│           └── logic/              Core inference pipeline
│               ├── binary.ts       Stage 1: binary gate (phish_binary.onnx)
│               ├── nlp.ts          Stage 2: intent classifier (phish_intent.onnx)
│               ├── fuse.ts         Signal assembly + weighted formula
│               ├── score.ts        Risk tier scoring with short-text dampening
│               ├── features.ts     Structural signal extraction
│               ├── auth.ts         SPF/DKIM/DMARC header parser (local)
│               ├── thread.ts       BEC thread-drift detector
│               ├── explain.ts      Reason generation
│               ├── extractEmail.ts Office.js email extraction
│               ├── extractLinks.ts Link extraction and domain parsing
│               ├── hash.ts         Message ID hashing (no content in logs)
│               ├── log.ts          Structured local logging
│               └── redact.ts       PII redaction for logs
│
├── ml/                             Machine learning pipeline (Python)
│   ├── train_phish_binary_full.py  Binary classifier training
│   ├── train_intent_full.py        Intent classifier training
│   ├── build_dataset.py            Corpus construction from Zenodo source
│   ├── export_onnx.py              HuggingFace → ONNX export
│   ├── eval_binary_v2.py           Primary classification metrics
│   ├── eval_baselines.py           TF-IDF and non-staged ONNX baselines
│   ├── eval_crossval.py            5-fold stratified cross-validation
│   ├── eval_staged.py              Staged compute efficiency
│   ├── eval_full_pipeline_latency.py   Pipeline latency measurement
│   ├── eval_threshold_sensitivity.py   Threshold sweep
│   ├── eval_adversarial.py         LLM-generated phishing detection
│   ├── eval_intent_labels.py       Intent model per-label evaluation
│   ├── privacy_audit.py            Network request interception audit
│   ├── generate_figures.py         Generates all paper figures from results/
│   ├── requirements.txt            Python dependencies
│   ├── data_processed/             Preprocessed corpus (33,105 emails)
│   ├── data_raw/synthetic_phishing/    200 LLM-generated phishing emails
│   └── export/onnx/                Trained ONNX models + tokenizer files
│
├── evaluation/
│   ├── results/                          Canonical JSON/CSV outputs
│   └── figures/                          Generated PDF figures
|   └── privacy_audit_browser.txt         Network audit log
|   └── check_canary_leakage.py           Canary Leak Checker Script
|   └── check_canary.md                   Canary script runbook
|   └── export_mitm_text_summary.py       MITM Flow file summary exporter script
|   └── privacy_audit_canary_report.jsonl Canary Search Result
│
├── docs/
│   ├── UI_TESTING_GUIDE.md         Add-in setup and testing walkthrough
│   └── UI_TEST_EMAILS.md           Curated test cases with expected outcomes
│
└── scripts/
    └── sync-models.ps1             Copies ONNX models into addin/public/models/
```

---

---

## Running the add-in

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Node.js 18 or later** | Required for the add-in development server. |
| **Model Artifacts** | **Required (~511MB).** Due to proxy size limitations, download manually from [**Figshare (Anonymous Private Link)**](https://figshare.com/s/da98f8dc86039fccf1d3). |
| **Microsoft 365 account** | Must support sideloading (Outlook Web or New Outlook for Windows). |
| **Python 3.10+** | Only required if re-running the evaluation scripts. |

---

### Step 1 — Install dependencies and trust the development certificate

```powershell
cd addin
npm install
npm run dev-certs
cd ..
```

`dev-certs` generates a self-signed localhost certificate required by
Outlook to load the add-in over HTTPS.

### Step 2 — Obtain and Sync ONNX Models

The large model artifacts (267MB each) are not stored directly in the repository due to proxy size limitations. You must place them in the correct directories before starting the server.

1. Download the two `.onnx` files from the [Anonymous Figshare Bundle](https://figshare.com/s/da98f8dc86039fccf1d3).
2. Place `phish_binary.onnx` and `phish_intent.onnx` into the `ml/export/onnx/` folder.
3. Run the sync script to move them into the add-in runtime directory:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\sync-models.ps1
  ```
Copies `ml/export/onnx/phish_binary.onnx` and `phish_intent.onnx` into
`addin/public/models/`.

### Step 3 — Start the development server

```powershell
cd addin
npm start
```

Server starts at `https://localhost:3000`.

**Note**: If you visit this URL directly in a web browser, you may see a "Cannot GET /" error. This is expected behavior. The server is designed to provide the add-in manifest and assets to the Outlook client via the sideloading process in Step 4, rather than hosting a standalone website.

### Step 4 — Sideload in Outlook

1. Open **Outlook Web** (`outlook.office.com`) or **New Outlook for Windows**.
2. Go to **Settings → Add-ins → Manage add-ins → Add from file**.
3. Upload `addin/manifest.dev.xml` (or `addin/manifest.xml` if you keep it pointed to localhost).
4. Open any email and click the **Outlook Phish Guard** button in the
   ribbon to open the taskpane.

### Step 5 — Enterprise production deployment (`[url]` placeholders)

The artifact intentionally uses `[url]` placeholders in production-hosted paths.
Before enterprise deployment, replace every `[url]` in `addin/manifest.production.xml`
with your live HTTPS host.

Also update the hosted model fallback in `addin/src/taskpane/logic/modelCache.ts`:

- `REMOTE_MODEL_ROOT = "[url]/models"` must be replaced with your live model URL root.

Use `addin/manifest.production.xml` for production rollout after replacement.
`SupportsPinning` is already enabled in the production manifest; taskpane pinning
is available when these URLs are valid and reachable.

### Step 6 — Test

Follow `docs/UI_TESTING_GUIDE.md` for a complete walkthrough.
`docs/UI_TEST_EMAILS.md` provides curated test inputs with expected outcomes.

---

## Re-running the evaluation

### Set up Python

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r ml\requirements.txt
```

### Run evaluation scripts

Each script reads from `ml/data_processed/` and `ml/export/onnx/` and
writes results to `evaluation/results/`.

```powershell
python ml\eval_binary_v2.py           # Primary classification metrics
python ml\eval_baselines.py           # Baseline comparison
python ml\eval_crossval.py            # 5-fold cross-validation
python ml\eval_staged.py              # Staged compute efficiency
python ml\eval_full_pipeline_latency.py  # Pipeline latency
python ml\eval_adversarial.py         # LLM-generated phishing detection
python ml\privacy_audit.py            # Network request audit
```

### Re-generate figures

```powershell
python ml\generate_figures.py
```

Reads only from `evaluation/results/` and writes PDFs to
`evaluation/figures/`.

---

## Model artifacts and verification

| File | Size | SHA-256 |
|------|------|---------|
| `ml/export/onnx/phish_binary.onnx` | 267,932,171 bytes | `e0b8970aa11ea7cbed718d8c0e01fa8851d1bb97bdbf73c2223d7ddcfb5b38cf` |
| `ml/export/onnx/phish_intent.onnx` | 267,938,323 bytes | `260ae858c5c5067954ba402fded0d32efdfc845a8cfb1821ca053de5857c1f0c` |

Hashes are also recorded in `ml/export/onnx/manifest.json`.
Both models are fine-tuned from `distilbert-base-uncased`. To verify:

```powershell
# PowerShell
Get-FileHash ml\export\onnx\phish_binary.onnx -Algorithm SHA256
```

```bash
# Linux / macOS
sha256sum ml/export/onnx/phish_binary.onnx
```

---

## Training corpus

Derived from the **Zenodo Phishing Email Curated Datasets**
(DOI: `10.5281/zenodo.8339691`). The preprocessed files in
`ml/data_processed/` are sufficient to re-run all evaluation scripts.

To rebuild from scratch from a Zenodo download:

```powershell
python ml\build_dataset.py --zenodo-dir <path-to-zenodo-download>
```

Raw Zenodo files are not included to avoid redistributing a third-party
dataset. The processed corpus is derived solely from that source.

---

## Synthetic phishing dataset

`ml/data_raw/synthetic_phishing/synthetic_phishing_200.jsonl` — 200
LLM-generated phishing emails for adversarial robustness evaluation.

Each record:

| Field | Description |
|-------|-------------|
| `id` | Sample identifier |
| `intent` | `credential_harvesting`, `payment_fraud`, `threat_language`, or `impersonation` |
| `generation_model` | Service-returned model string |
| `subject` | Email subject |
| `body` | Email body text |
| `detected_tau025` | Detection result at τ = 0.25 |
| `prompt_template` | Generation prompt |

All emails use fictional names, organizations, addresses, and URLs. No
generated email was sent to any individual.

---

## Evidence chain

Every metric traces to a file in `evaluation/results/`.

| Claim | Source |
|-------|--------|
| τ = 0.25: P 0.9866 / R 0.9916 / F1 0.9891 / FPR 0.41% | `binary_eval_v2.json` |
| τ = 0.90: P 0.9916 / R 0.9807 / F1 0.9861 / FPR 0.26% | `binary_eval_v2.json` |
| ROC-AUC 0.9995, PR-AUC 0.9983 | `threshold_sensitivity.json` |
| 5-fold CV: F1 0.9896 ± 0.0022 | `crossval.json` |
| Staged savings 76.38% at τ = 0.25 | `staged_efficiency.json` |
| Stage 1 mean 40.7 ms, P95 45.8 ms | `stage1_latency.csv` |
| Combined pipeline mean 82.2 ms, P95 89.7 ms | `full_pipeline_latency.json` |
| Privacy audit: 0 outbound requests / 100 emails | `privacy_audit.json` |
| Adversarial overall 82.5% at τ = 0.25 | `adversarial_eval.json` |
| Intent micro F1 0.816, macro F1 0.497 | `intent_labels_eval.json` |

Full canonical metric index with per-field source tracing: `PAPER_NUMBERS.md`.

---

## Latency measurement scope

Latency values are measured using Python `onnxruntime` CPU provider,
timing `session.run()` exclusively with 3 warmup passes. Tokenization
time is excluded. These measurements isolate model inference cost and
do not capture end-to-end browser UI latency, Outlook Office.js mailbox
extraction overhead, or browser scheduling effects.

The deployed add-in uses `onnxruntime-web` with the WASM execution provider
under a single-threaded constraint (`SharedArrayBuffer` is unavailable in
the Outlook taskpane context under current browser security configurations).

---

## Privacy properties

The add-in does not transmit email subject, body, sender address, or any
content fragment off-device during analysis:

- All ONNX inference runs locally in a WebAssembly sandbox
- `auth.ts` reads `Authentication-Results` from the locally delivered email
  item; no external DNS queries are performed
- Logged data contains only locally computed hashed message identifiers,
  risk tier, and reason codes — no message content

The privacy boundary is verified empirically; see
`evaluation/results/privacy_audit.json`.

---

## Deliberate exclusions

| Excluded | Reason |
|---------|--------|
| `addin/node_modules/` | Install via `npm install` |
| Raw Zenodo source corpora | Large third-party dataset; not required |
| Training checkpoints `ml/runs/` | Not needed; ONNX artifacts are the relevant outputs |

---

## Re-training from scratch

```powershell
python ml\build_dataset.py --zenodo-path <path>
python ml\train_phish_binary_full.py
python ml\train_intent_full.py
python ml\export_onnx.py
powershell -ExecutionPolicy Bypass -File .\scripts\sync-models.ps1
```

Re-trained models will differ slightly from the shipped artifacts due to
random initialization. The shipped ONNX files are what produced all
reported metrics.
