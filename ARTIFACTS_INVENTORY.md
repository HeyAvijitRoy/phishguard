# Artifacts Inventory

Generated on 2026-04-01 for the current contents inside `artifacts`.

Total entries: 127

```text
|   ARTIFACTS_INVENTORY.md
|   README.md
|
+---addin
|   |   manifest.xml
|   |   package.json
|   |   tsconfig.json
|   |   webpack.config.js
|   |
|   +---assets
|   |       icon-16.png
|   |       icon-32.png
|   |       icon-64.png
|   |       icon-80.png
|   |       icon-128.png
|   |
|   +---public
|   |   \---models
|   |           README.txt
|   |
|   \---src
|       |   index.tsx
|       |   support.html
|       |   global.d.ts
|       |
|       +---shared
|       |       types.ts
|       |
|       \---taskpane
|           |   taskpane.html
|           |   Taskpane.tsx
|           |
|           +---components
|           |       ActionButtons.tsx
|           |       Controls.tsx
|           |       LinkInspector.tsx
|           |       ReasonsList.tsx
|           |       RiskBanner.tsx
|           |
|           +---logic
|           |       auth.ts
|           |       binary.ts
|           |       explain.ts
|           |       extractEmail.ts
|           |       extractLinks.ts
|           |       features.ts
|           |       fuse.ts
|           |       hash.ts
|           |       log.ts
|           |       nlp.ts
|           |       redact.ts
|           |       score.ts
|           |       thread.ts
|           |
|           \---styles
|                   taskpane.css
|
+---docs
|   |   UI_TESTING_GUIDE.md
|   |   UI_TEST_EMAILS.md
|   |
|   \---ui_test_emails
|           Catch up on GTC with 700+ sessions now available on demand.eml
|           Don’t miss out Start your SC-200 Security Certification today.eml
|           Q3 team meeting — agenda attached.eml
|           Your Microsoft 365 account will be suspended in 24 hours.eml
|
+---evaluation
|   +---figures
|   |       fig_baseline_comparison.pdf
|   |       fig_confusion_matrix.pdf
|   |       fig_crossval.pdf
|   |       fig_intent_per_label.pdf
|   |       fig_latency_comparison.pdf
|   |       fig_latency_stage1.pdf
|   |       fig_pr_curve.pdf
|   |       fig_roc_curve.pdf
|   |       fig_staged_efficiency.pdf
|   |       fig_threshold_sensitivity.pdf
|   |
|   \---results
|           adversarial_eval.json
|           baselines.json
|           binary_eval_v2.json
|           crossval.json
|           full_pipeline_latency.json
|           intent_labels_eval.json
|           privacy_audit.json
|           stage1_latency.csv
|           stage2_latency_tau090.csv
|           staged_efficiency.json
|           synthetic_phishing_stats.json
|           threshold_sensitivity.json
|
+---ml
|   |   build_dataset.py
|   |   eval_adversarial.py
|   |   eval_baselines.py
|   |   eval_binary_v2.py
|   |   eval_crossval.py
|   |   eval_full_pipeline_latency.py
|   |   eval_intent_labels.py
|   |   eval_staged.py
|   |   eval_threshold_sensitivity.py
|   |   export_onnx.py
|   |   generate_figures.py
|   |   privacy_audit.py
|   |   requirements.txt
|   |   threshold_sweep.py
|   |   train_intent_full.py
|   |   train_phish_binary_full.py
|   |
|   +---data_processed
|   |       email_corpus.jsonl
|   |       hard_negatives.jsonl
|   |       stats.json
|   |       train_intent.jsonl
|   |       val_intent.jsonl
|   |
|   +---data_raw
|   |   \---synthetic_phishing
|   |           batch_01_credential.json
|   |           batch_02_credential.json
|   |           batch_03_payment.json
|   |           batch_04_payment.json
|   |           batch_05_threat.json
|   |           batch_06_threat.json
|   |           batch_07_impersonation.json
|   |           batch_08_impersonation.json
|   |           synthetic_phishing_200.jsonl
|   |
|   \---export
|       \---onnx
|               config.json
|               labels.json
|               manifest.json
|               phish_binary.onnx
|               phish_binary_labels.json
|               phish_intent.onnx
|               smoke_test_result.txt
|               special_tokens_map.json
|               tokenizer.json
|               tokenizer_config.json
|               vocab.txt
|
\---scripts
        sync-models.ps1
```
