import type { AuthSignals, EmailFeatures, NlpSignals, Reason, ThreadSignals } from "../../shared/types";

type FusedSignals = EmailFeatures & { nlp?: NlpSignals; auth?: AuthSignals; thread?: ThreadSignals };

export function buildReasons(fused: FusedSignals): Reason[] {
  const reasons: Reason[] = [];

  if (fused.credHits.length) {
    reasons.push({
      code: "CRED_REQUEST",
      title: "Credential request language",
      detail: "This message includes terms commonly used to request passwords, login, or MFA codes.",
      strength: "high",
      evidence: fused.credHits.slice(0, 5)
    });
  }

  if (fused.paymentHits.length) {
    reasons.push({
      code: "PAYMENT_REQUEST",
      title: "Payment / finance request language",
      detail: "This message includes payment or banking-related terms commonly used in payment redirection scams.",
      strength: "high",
      evidence: fused.paymentHits.slice(0, 5)
    });
  }

  if (fused.threatHits.length) {
    reasons.push({
      code: "THREAT_LANGUAGE",
      title: "Threat or account lockout language",
      detail: "This message uses language that pressures you with loss of access or negative consequences.",
      strength: "medium",
      evidence: fused.threatHits.slice(0, 5)
    });
  }

  if (fused.urgencyHits.length) {
    reasons.push({
      code: "URGENCY_LANGUAGE",
      title: "Urgency cues",
      detail: "This message contains urgent calls-to-action often used to reduce careful checking.",
      strength: "medium",
      evidence: fused.urgencyHits.slice(0, 5)
    });
  }

  if ((fused.linkFlags["DISPLAY_MISMATCH"] ?? 0) > 0) {
    reasons.push({
      code: "LINK_DISPLAY_MISMATCH",
      title: "Link text may not match destination",
      detail: "Some links appear to present one domain but actually point elsewhere. Verify the domain before clicking.",
      strength: "high"
    });
  }

  if ((fused.linkFlags["PUNYCODE"] ?? 0) > 0) {
    reasons.push({
      code: "LINK_PUNYCODE",
      title: "Possible lookalike domain (punycode)",
      detail: "At least one link uses punycode, which can be used for lookalike domains.",
      strength: "high"
    });
  }

  if ((fused.linkFlags["SHORTENER"] ?? 0) > 0) {
    reasons.push({
      code: "LINK_SHORTENER",
      title: "Shortened link",
      detail: "Shortened URLs can hide the real destination. Consider inspecting or expanding the URL before visiting.",
      strength: "medium"
    });
  }

  if ((fused.linkFlags["IP_HOST"] ?? 0) > 0) {
    reasons.push({
      code: "LINK_IP_HOST",
      title: "IP-based link destination",
      detail: "Links that use raw IP addresses are uncommon for legitimate login/payment flows.",
      strength: "high"
    });
  }

  if ((fused.linkFlags["MANY_SUBDOMAINS"] ?? 0) > 0) {
    reasons.push({
      code: "LINK_MANY_SUBDOMAINS",
      title: "Excessive subdomains",
      detail: "Some links have many subdomains, which can be used to impersonate legitimate sites.",
      strength: "low"
    });
  }

  if (fused.senderLinkMismatch) {
    const evidence: string[] = [];
    if (fused.senderDomain) evidence.push(`sender: ${fused.senderDomain}`);
    if (fused.primaryCtaDomain) evidence.push(`primary link: ${fused.primaryCtaDomain}`);
    else if (fused.linkDomains.length) evidence.push(`links: ${fused.linkDomains.slice(0, 3).join(", ")}`);
    reasons.push({
      code: "SENDER_LINK_MISMATCH",
      title: fused.primaryCtaDomain ? "Sender and primary link domains differ" : "Sender and link domains differ",
      detail: "The sender domain does not match the primary link domain. This is a supporting phishing cue.",
      strength: fused.senderLinkMismatchPrimary ? "medium" : "low",
      evidence: evidence.length ? evidence : undefined
    });
  }

  if (fused.auth?.available) {
    if (fused.auth.dkim === "fail") {
      reasons.push({
        code: "AUTH_DKIM_FAIL",
        title: "DKIM failed",
        detail: "The sender's DKIM authentication failed. This can indicate spoofing.",
        strength: "high"
      });
    }
    if (fused.auth.spf === "fail") {
      reasons.push({
        code: "AUTH_SPF_FAIL",
        title: "SPF failed",
        detail: "The sender domain failed SPF checks. This can indicate spoofing.",
        strength: "high"
      });
    }
    if (fused.auth.dmarc === "fail") {
      reasons.push({
        code: "AUTH_DMARC_FAIL",
        title: "DMARC failed",
        detail: "DMARC alignment failed for this sender. This is a strong spoofing signal.",
        strength: "high"
      });
    }
  } else if (fused.auth) {
    reasons.push({
      code: "AUTH_UNAVAILABLE",
      title: "Authentication signals unavailable",
      detail: "Auth headers are not available in this mode. Enable enterprise mode for DKIM/SPF/DMARC signals.",
      strength: "low"
    });
  }

  if (fused.thread?.nameSameAddressChanged) {
    reasons.push({
      code: "THREAD_NAME_ADDRESS_CHANGE",
      title: "Conversation anomaly",
      detail: "The same display name appears with multiple sender domains in this thread.",
      strength: "medium",
      evidence: fused.thread.evidence
    });
  }

  const intentCredential = fused.nlp?.intentCredential ?? 0;
  if (intentCredential >= 0.85) {
    reasons.push({
      code: "NLP_INTENT_CREDENTIAL",
      title: "Semantic intent: credential harvesting",
      detail: "The semantic intent suggests credential collection, which is a common phishing goal.",
      strength: "high"
    });
  }

  const intentPayment = fused.nlp?.intentPayment ?? 0;
  if (intentPayment >= 0.85) {
    reasons.push({
      code: "NLP_INTENT_PAYMENT",
      title: "Semantic intent: payment redirection",
      detail: "The semantic intent suggests payment redirection or financial diversion.",
      strength: "high"
    });
  }

  const intentThreat = fused.nlp?.intentThreat ?? 0;
  if (intentThreat >= 0.85) {
    reasons.push({
      code: "NLP_INTENT_THREAT",
      title: "Semantic intent: account threat",
      detail: "The semantic intent suggests threats or account lockout language.",
      strength: "high"
    });
  }

  const intentImpersonation = fused.nlp?.intentImpersonation ?? 0;
  if (intentImpersonation >= 0.85) {
    reasons.push({
      code: "NLP_INTENT_IMPERSONATION",
      title: "Semantic intent: impersonation",
      detail: "The semantic intent suggests impersonation or authority cues.",
      strength: "high"
    });
  }

  // Weak style anomalies (kept low to avoid unfairness)
  const styleFlags = [];
  if (fused.exclamCount >= 3) styleFlags.push("many exclamation marks");
  if (fused.allCapsTokenCount >= 3) styleFlags.push("multiple ALL-CAPS tokens");
  if (fused.nonAsciiCount >= 10) styleFlags.push("unusual character patterns");

  if (styleFlags.length) {
    reasons.push({
      code: "STYLE_ANOMALY",
      title: "Unusual writing style",
      detail: "Some stylistic patterns are less common in normal business email. This is a weak signal by itself.",
      strength: "low",
      evidence: styleFlags
    });
  }

  // Combo reason: strong when link + credential appear together
  if (fused.credHits.length && fused.linkCount > 0) {
    reasons.push({
      code: "SUSPICIOUS_COMBO",
      title: "High-risk combination",
      detail: "Credential-request language combined with clickable links is a common phishing pattern.",
      strength: "high"
    });
  }

  // Sort: high -> medium -> low
  const order = { high: 0, medium: 1, low: 2 } as const;
  reasons.sort((a, b) => order[a.strength] - order[b.strength]);

  return reasons;
}
