# PhishGuard — UI Test Emails

This document provides curated test cases for manually validating the PhishGuard Outlook add-in. Test cases cover the three primary UI states (high risk, low risk, and the known BEC detection limitation) as well as edge cases that verify the false positive suppression logic.

All expected outcomes assume the deployed add-in gate threshold `τ = 0.90`. For the research threshold `τ = 0.25`, more emails will pass the gate and receive Stage 2 analysis, but the risk tier displayed may differ.

---

## How to use these test cases

1. Start the add-in following [UI_TESTING_GUIDE.md](UI_TESTING_GUIDE.md).
2. Open a new email compose window in Outlook.
3. Paste the subject and body text below into the compose window and send it to yourself, or use the Outlook Web developer compose view.
4. Open the received email and click the PhishGuard taskpane button.
5. Compare the displayed risk tier and reason labels against the expected outcome.

---

## A — High-risk set

These emails contain clear phishing signals and should trigger the binary gate, complete Stage 2 analysis, and display a high-risk red banner.

### A1 — Credential harvesting

**Subject:** `URGENT: Your Microsoft 365 account will be suspended`

**Body:**
```
Dear Account Holder,

Our security systems have detected unusual sign-in activity on your
Microsoft 365 account. To protect your account, we have temporarily
limited your access.

To restore full access, you must verify your identity immediately:

VERIFY YOUR ACCOUNT NOW →
https://verify-account.microsoftsecure-portal.com/confirm

This link expires in 24 hours. If you do not verify, your account will
be permanently suspended and all emails will be deleted.

Do not ignore this message. This is your final notice.

Microsoft Account Security Team
```

**Expected:**
- Risk tier: High (red banner)
- Stage 2 runs
- Reasons include: credential request language, urgency cues, sender/link
  domain mismatch (link domain differs from sender domain)
- `phishProb` typically > 0.99

---

### A2 — Payment fraud / wire transfer

**Subject:** `Urgent wire transfer required — confidential`

**Body:**
```
Hi,

I need you to process an urgent wire transfer today. This is time-sensitive
and must be handled confidentially before close of business.

Amount: $47,500.00
Beneficiary: Global Trade Partners Ltd
Account: 8823-44019-002
Routing: 021000021
Bank: First National

Do not discuss this with anyone else. Do not call to verify — I am in
back-to-back meetings. Process immediately and confirm by email only.

Thanks
```

**Expected:**
- Risk tier: High or Medium
- Stage 2 runs
- Reasons include: payment/finance request language, urgency cues,
  possibly semantic intent: payment fraud

---

### A3 — Threat language / legal coercion

**Subject:** `FINAL WARNING: Legal action pending against your account`

**Body:**
```
NOTICE OF PENDING LEGAL ACTION

This is your final notice before legal proceedings are initiated
against your account for outstanding charges.

You have 48 hours to respond or your case will be forwarded to our
collections department and credit reporting agencies.

Click here to review your case and make payment to avoid further action:
https://dispute-resolution.account-verify.net/case/38821

Failure to respond will result in:
- Credit score impact
- Collection fees added to outstanding balance
- Possible legal proceedings

RESPOND WITHIN 48 HOURS

Collections & Dispute Resolution Team
```

**Expected:**
- Risk tier: High
- Stage 2 runs
- Reasons include: threat or account lockout language, urgency cues,
  sender/link domain mismatch

---

### A4 — IT helpdesk impersonation

**Subject:** `IT Security: Your VPN credentials have been compromised`

**Body:**
```
Hello,

Our security monitoring has detected that your VPN credentials may have
been exposed in a recent credential dump.

To protect your access, please reset your password immediately using
the secure link below:

https://it-helpdesk.corp-security-portal.com/vpn-reset

You must complete this within 2 hours or your VPN access will be
suspended as a precautionary measure.

If you did not initiate this request, contact the IT Security team
immediately at security@corp-security-portal.com.

IT Security Team
Help Desk Operations
```

**Expected:**
- Risk tier: High
- Stage 2 runs
- Reasons include: credential request language, urgency cues, threat
  language, sender/link domain mismatch

---

## B — Low-risk set

These emails should be resolved by the binary gate alone (Stage 2 does
not run) and display no warning banner.

### B1 — Routine internal business email

**Subject:** `Q3 planning meeting — agenda attached`

**Body:**
```
Hi team,

Just a reminder that our Q3 planning meeting is scheduled for Thursday
at 2pm in Conference Room B.

Agenda items:
- Q2 performance review
- Budget planning for Q3
- Team capacity discussion
- Any other business

Please review the attached Q3 report before the meeting so we can have
a productive discussion.

Let me know if you have any conflicts.

Thanks
```

**Expected:**
- Risk tier: Low (no warning banner)
- Stage 2 does NOT run
- `phishProb` typically < 0.05
- `DONE: gated score=0` in debug output

---

### B2 — Tech newsletter

**Subject:** `This week in security: AI updates and threat intelligence`

**Body:**
```
This Week in Security

AI-assisted threat detection continues to evolve rapidly. Researchers
at several institutions have published findings on adversarial robustness
in NLP-based email classifiers.

In other news, a new phishing campaign targeting finance teams has been
documented by CISA, using BEC-style impersonation without malicious links.

Read more on our website. To unsubscribe from this newsletter, click
the link at the bottom of this message.

The Security Digest Team
```

**Expected:**
- Risk tier: Low
- Stage 2 does NOT run

---

### B3 — Calendar invitation

**Subject:** `Invitation: Project review — April 15, 2026`

**Body:**
```
You are invited to the following meeting:

Project review — Q2 deliverables
Date: April 15, 2026
Time: 10:00 AM – 11:00 AM
Location: Room 4B / Teams

Agenda: Review Q2 deliverable status, identify blockers, assign follow-up
action items.

Please accept or decline using your calendar application.
```

**Expected:**
- Risk tier: Low
- Stage 2 does NOT run

---

### B4 — Promotional urgency (false positive test)

**Subject:** `Last chance: 40% off expires tonight`

**Body:**
```
Hi,

This is your last chance to save 40% on your subscription before our
sale ends tonight at midnight.

Don't miss out — this offer expires in just a few hours.

What's included:
- Unlimited access to all premium features
- Priority customer support
- Advanced analytics dashboard
- Team collaboration tools

Use code SAVE40 at checkout:
https://checkout.yourapp.com/upgrade?code=SAVE40

If you have questions, contact support at support@yourapp.com

The Team
```

**Expected:**
- Risk tier: Low or Medium depending on the deployed threshold
- If Medium is displayed, this is a documented false positive pattern:
  promotional urgency language overlaps with phishing vocabulary
- Stage 2 may run (binary model scores this category high due to urgency
  phrasing and time-pressure language)
- This case is discussed in the paper's error analysis section

**Note on this case:** The short-text dampening and signal-stacking
requirements in `score.ts` are specifically designed to suppress false
positive warnings for this category. If the add-in shows Low for this
email, the suppression logic is working correctly.

---

## C — Known-limitation set

These cases document the system's known ceiling for content-based detection.
They are included to demonstrate honest evaluation of the system, not as
cases that should be improved before running.

### C1 — BEC impersonation (content-only miss)

**Subject:** `Quick favor needed`

**Body:**
```
Hi,

Are you available? I need a quick favor — could you process a vendor
payment today? I'm tied up in meetings and can't step away.

Just need you to take care of it before end of day. I'll explain more
when we speak.

Thanks
```

**Expected:**
- Risk tier: Low
- Stage 2 does NOT run (or runs but scores very low)
- **This is the correct behavior** — the email contains no detectable
  phishing signals at the content level
- This is the BEC impersonation gap documented in the paper:
  contextual trust attacks are semantically indistinguishable from
  legitimate email at the content level
- In a real deployment, `auth.ts` (SPF/DKIM/DMARC failures) and
  `thread.ts` (display-name/domain drift in reply chains) would provide
  identity-level signals that content analysis cannot

---

### C2 — Vendor bank-change notice

**Subject:** `Updated banking details for your account`

**Body:**
```
Dear Finance Team,

Please be advised that we have updated our banking details due to a
system migration. All future payments should be directed to our new
account effective immediately.

New banking information:
Bank: Meridian Business Bank
Account name: Acme Supplies Ltd
Routing: 021-77832
Account: 9034512876

Please update your records and confirm receipt of this notice.

If you have any questions about this change, please contact our
accounts team directly.

Kind regards,
Accounts Department
Acme Supplies Ltd
```

**Expected:**
- Risk tier: Medium (payment fraud signals fire)
- Stage 2 runs
- Reasons include: payment/finance request language, semantic intent:
  payment redirection, urgency cues
- `phishProb` typically > 0.99
- This is a legitimate false positive pattern: real vendor bank-change
  notifications have the same vocabulary as fraudulent ones. The intent
  classifier correctly identifies the payment redirection pattern. Without
  auth signals confirming the sender's domain identity, the system correctly
  escalates this to Medium risk.

---

## What to record for each test for futher analysis

| Field | Description |
|-------|-------------|
| Risk tier shown | Low / Medium / High |
| Stage 2 ran | Yes / No (visible in debug output) |
| Reason labels | List the reason codes shown in the taskpane |
| `phishProb` | From the debug panel at the bottom of the taskpane |
| `score` | From the debug panel |
| Screenshot filename | If captured |
| Unexpected behavior | Any deviation from expected outcome above |

The debug panel (visible during development builds) shows:
```
phishProb=<value>  gate=<threshold>
DONE: score=<value>  reasons=<count>
```

If Stage 2 did not run, the debug output shows `gated score=0` instead
of a computed score.
