# PhishGuard — UI Testing Guide

This guide walks through setting up the PhishGuard Outlook add-in from the
artifact bundle, running it against test emails, and interpreting the output.
It is intended for anyone evaluating the artifact or verifying that the
deployed system behaves as described in the paper.

---

## What this guide covers

1. Full setup from the artifact bundle to a running add-in
2. How to analyze an email and read the output
3. Systematic test procedure covering all three UI states
4. How to observe latency in the browser (supplementary)
5. Smoke test: verifying the artifact is self-contained

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Node.js 18 or later | [nodejs.org](https://nodejs.org) |
| Microsoft 365 account | Must support sideloading Office add-ins |
| Outlook Web or New Outlook for Windows | Required for sideloading; classic Outlook does not support task pane add-ins from localhost |
| Git (optional) | Only needed if cloning; not required if using the archive download |

---

## Setup

### 1. Install Node dependencies

From the root of the artifact bundle:

```powershell
cd addin
npm install
cd ..
```

This installs the TypeScript compiler, webpack, `onnxruntime-web`, and all
other add-in dependencies into `addin/node_modules/`.

### 2. Trust the development certificate

```powershell
cd addin
npm run dev-certs
cd ..
```

This generates a self-signed certificate for `https://localhost:3000`.
Outlook requires HTTPS to load task pane add-ins. You may see an OS-level
prompt asking whether to trust the certificate — accept it.

On macOS, you may need to run this with `sudo`. On Linux, the certificate
must be added to the system trust store manually; the command will print
instructions.

### 3. Copy the ONNX models into the add-in

```powershell
cd ../
powershell -ExecutionPolicy Bypass -File .\scripts\sync-models.ps1
```

This copies `phish_binary.onnx` and `phish_intent.onnx` from
`ml/export/onnx/` into `addin/public/models/`. The add-in loads models
from this path at runtime.

**Verify the copy succeeded:**

```powershell
ls addin\public\models\
```

You should see both `.onnx` files there. If the directory is empty, the
sync script did not run correctly — check the script output for errors.

### 4. Start the development server

```powershell
cd addin
npm start
```

The webpack dev server starts at `https://localhost:3000` and watches for
file changes. Leave this terminal running while you test.

You should see output ending with something like:

```
webpack compiled successfully
```

If you see SSL or certificate errors at this point, re-run `npm run dev-certs`.

### 5. Sideload the add-in in Outlook

**Outlook Web:**

1. Open `https://outlook.office.com` and sign in.
2. Click the settings gear → **Add-ins** → **Manage add-ins**.
3. Click **Add from file** → **Browse** → select `addin/manifest.xml`.
4. Click **Add** to install.

**New Outlook for Windows:**

1. Open New Outlook (the updated Windows 11 version, not classic Outlook).
2. Click the settings gear → **Add-ins** → **Manage add-ins** →
   **Add from file**.
3. Select `addin/manifest.xml` → click **Add**.

**Verify the sideload succeeded:**

Open any email. In the message reading pane, look for the **Outlook Phish Guard**
button in the top toolbar or ribbon. If you see it, the add-in loaded. Click it
to open the taskpane.

---

## Analyzing an email

1. Open an email in the Outlook reading pane.
2. Click **Outlook Phish Guard** in the toolbar to open the taskpane.
3. Click **Analyze** in the taskpane.

The add-in will analyze the email and display one of three states:

### State 1 — Low risk (no banner)

The taskpane shows a quiet confirmation that the email passed all security
checks. No warning banner, no reasons list, no action buttons. This is the
correct display for 76% of emails — the binary gate resolved the email
without running Stage 2.

The debug panel (bottom of the taskpane) will show:
```
phishProb=<low value>  gate=0.9
DONE: gated score=0
```

### State 2 — Medium risk (amber banner)

The taskpane shows a yellow/amber banner with the label **Suspicious email
— review carefully**. The reasons list is visible. Action buttons are shown
(Dismiss, Learn why, Inspect links, Report phishing).

The debug panel will show:
```
phishProb=<value ≥ 0.9>  gate=0.9
DONE: score=<25-69>  reasons=<count>
```

### State 3 — High risk (red banner)

The taskpane shows a red banner with the label **High phishing risk
detected**. The reasons list shows 5-7 items. Report phishing button is
prominently displayed.

The debug panel will show:
```
phishProb=<value ≥ 0.9>  gate=0.9
DONE: score=<≥70>  reasons=<count>
```

---

## Systematic test procedure

Use `UI_TEST_EMAILS.md` for the full set of test cases. Below is a
suggested order that efficiently covers all three UI states.

### Test 1 — Verify high-risk detection (A1 from UI_TEST_EMAILS.md)

Purpose: confirm the full pipeline runs and the red banner appears.

Paste the A1 credential-harvesting email body into an email, send it to
yourself, open it, and analyze it. Expected: High risk, score = 100, seven
reason codes including credential request language, urgency cues, and
sender/link domain mismatch.

**What to check:**

- [ ] Red banner appears
- [ ] At least 5 reason labels are visible in the WHY THIS WAS FLAGGED list
- [ ] Clicking **Learn why** expands the plain-English explanations
- [ ] Clicking **Inspect links** shows the extracted link domains
- [ ] Debug panel shows `phishProb > 0.99`, `score = 100`

### Test 2 — Verify low-risk gating (B1 from UI_TEST_EMAILS.md)

Purpose: confirm the binary gate suppresses Stage 2 for routine email.

Paste the B1 routine business email body and analyze it.
Expected: Low risk, no banner, Stage 2 did not run.

**What to check:**

- [ ] No warning banner
- [ ] Taskpane shows "No phishing signals detected" or similar
- [ ] Debug panel shows `phishProb < 0.10` and `gated score=0`

### Test 3 — Verify the BEC limitation (C1 from UI_TEST_EMAILS.md)

Purpose: document the known ceiling of content-based BEC detection.

Paste the C1 BEC impersonation email body and analyze it.  
Expected: Low risk.

**What to check:**

- [ ] Low risk, no banner
- [ ] Debug panel shows low phishProb
- [ ] This is the correct behavior — the paper documents this limitation

### Test 4 — Verify medium-risk with payment fraud (C2 from UI_TEST_EMAILS.md)

Purpose: confirm payment fraud language triggers Stage 2 and medium risk.

Paste the C2 vendor bank-change email body and analyze it.  
Expected: Medium risk, payment-related reasons in the reasons list.

**What to check:**

- [ ] Amber banner appears
- [ ] Reason labels include payment/finance language
- [ ] Debug panel shows `phishProb > 0.99` (binary model is confident)
  and `score` in the medium range (25–69)
- [ ] This case shows the system detecting social engineering without any
  malicious links

### Test 5 — Verify false positive suppression (B4 from UI_TEST_EMAILS.md)

Purpose: check that promotional urgency email is handled gracefully.

Paste the B4 promotional urgency email body and analyze it.  
Expected: Low or Medium risk.

**What to check:**

- [ ] If Low: the dampening and signal-stacking logic is suppressing the
  false positive — correct behavior
- [ ] If Medium: document this as a false positive case consistent with the
  paper's error analysis section
- [ ] Debug panel shows `phishProb > 0.9` (binary model fires) but final
  displayed tier may differ due to scoring

---

## Observing browser-side latency (optional)

The canonical latency values in the paper are from the Python
`onnxruntime` CPU measurement (`eval_full_pipeline_latency.py`).
Browser-side timing includes additional overhead from Office.js mailbox
extraction and browser scheduling that the Python harness does not capture.

To observe browser-side inference timing:

1. Open browser DevTools (F12) → **Performance** tab.
2. Click **Record**, then analyze an email in the taskpane.
3. Stop recording and look for ONNX session calls in the flame graph.

Alternatively, if you want to add temporary timing instrumentation:

1. Open `addin/src/taskpane/logic/binary.ts`.
2. Add `performance.mark('stage1-start')` before the `session.run()` call
   and `performance.mark('stage1-end')` after it.
3. Add `performance.measure('stage1', 'stage1-start', 'stage1-end')`.
4. Reload the add-in dev server (`npm start`) and re-analyze.
5. In DevTools → **Performance** → look for `stage1` in the measure entries.

Browser-side timings will be higher than the Python harness values due to
WASM startup overhead, browser security sandboxing, and single-threaded
execution constraints (`SharedArrayBuffer` is unavailable in the Outlook
taskpane context). These are the actual deployment constraints.

---

## Artifact smoke test

Use this checklist to confirm that the artifact bundle is self-contained
and requires no external knowledge beyond what `README.md` documents.

- [ ] `npm install` runs to completion from a clean checkout
- [ ] `npm run dev-certs` completes without errors
- [ ] `sync-models.ps1` copies both `.onnx` files into `addin/public/models/`
- [ ] `npm start` starts the dev server at `https://localhost:3000`
- [ ] `addin/manifest.xml` sideloads successfully in Outlook
- [ ] Clicking Analyze on an email produces a result in the taskpane
- [ ] A high-risk email (test A1) shows a red banner with reason labels
- [ ] A routine email (test B1) shows no banner

If any step fails, note the error. Most common issues:

| Issue | Likely cause | Fix |
|-------|-------------|-----|
| `npm install` fails | Node version < 18 | Upgrade Node.js |
| Dev server SSL error | Certificate not trusted | Re-run `npm run dev-certs`, accept the OS prompt |
| Add-in loads but shows no result | ONNX models not in `addin/public/models/` | Re-run `sync-models.ps1` |
| `session is not defined` error | Model failed to load | Check browser console; confirm model file sizes match manifest hashes |
| Manifest sideload rejected | Outlook version too old | Use Outlook Web instead of desktop |

---

## Interpreting the debug panel

The debug panel at the bottom of the taskpane (visible in development
builds) shows the key signals for the analyzed email:

```
hasOffice=true | hasContext=true | hasMailbox=true | hasItem=true
host=Outlook | platform=OfficeOnline
subjectLen=<chars> | bodyLen=<chars>
linksFound=<count>
phishProb=<0.0–1.0>  gate=0.9
DONE: score=<0–100>  reasons=<count>
```

| Field | Meaning |
|-------|---------|
| `phishProb` | Stage 1 binary model output. Values ≥ 0.90 trigger Stage 2. |
| `gate` | The deployed gate threshold (0.9 in production) |
| `score` | Composite integer score from `score.ts` (0–100) |
| `reasons` | Number of distinct reasons shown in the WHY THIS WAS FLAGGED list |

If Stage 2 did not run (binary gate blocked), the output shows:
```
DONE: gated score=0
```

If Stage 2 ran, the score and reason count reflect the full multi-signal
analysis. `score ≥ 70` with `strongEvidenceCount ≥ 2` produces High risk.
`score ≥ 25` with at least one strong evidence signal produces Medium risk.
