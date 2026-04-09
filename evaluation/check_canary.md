# Canary Leakage Audit

Use this workflow to scan a saved mitmproxy capture for accidental leakage of known canary strings.

## 1. Check the Python dependency

First check whether `mitmproxy` is already available in the environment you plan to use:

```powershell
python -c "import mitmproxy; print(mitmproxy.__version__)"
```

If that import fails, create and use an isolated virtual environment named `mitm-env` so the global Python environment is not modified:

```powershell
python -m venv mitm-env
mitm-env\Scripts\Activate.ps1
python -m pip install mitmproxy
```

If you already have a `mitm-env`, activate it before running the audit commands.

## 2. Run the canary audit

Example using the audit capture in `evaluation/`:

```powershell
python evaluation/check_canary_leakage.py `
  --flows evaluation/privacy_audit_browser.mitm `
  --canary-subject "PHISHGUARD_CANARY_SUBJECT_7F3A91" `
  --canary-body "PHISHGUARD_CANARY_BODY_29C8D4 unique payroll token" `
  --report evaluation/privacy_audit_canary_report.jsonl
```

Notes:

- Repeat `--canary-subject` and `--canary-body` for multiple canaries.
- Use `--hosts outlook.live.com --hosts login.microsoftonline.com` to restrict scanning to specific hosts.
- The script exits with code `0` when no canaries are found and `1` when a match is found.

## 3. Review the JSONL report

The report is written to the path provided with `--report`. Each line is a self-contained JSON object recording the pass/fail verdict, the number of flows inspected, the canary tested, and any match details. The released artifact includes `evaluation/privacy_audit_canary_report.jsonl` containing the full canary scan results for the browser-path audit session.

## 4. Export a compact flow summary

If you want a quick text dump of the same capture, run:

```powershell
python evaluation/export_mitm_text_summary.py --flows evaluation/privacy_audit_browser.mitm
```

This prints one line per request with method, host, path, request body size, and response body size. A pre-generated copy is available at `evaluation/privacy_audit_browser.txt`.