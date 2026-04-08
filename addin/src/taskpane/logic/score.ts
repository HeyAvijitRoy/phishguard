import type { AuthSignals, ConfidenceBand, EmailFeatures, NlpSignals, RiskLabel, ThreadSignals } from "../../shared/types";

type FusedSignals = EmailFeatures & { nlpPoints?: number; nlp?: NlpSignals; auth?: AuthSignals; thread?: ThreadSignals };

// --- Hotfix: no-retrain calibration knobs ---
const SHORT_TEXT_BODYLEN_MAX = 220;      // tune: 150–300
const VERY_SHORT_BODYLEN_MAX = 90;       // tune: 60–120
const SHORT_TEXT_DAMPEN = 0.55;          // tune: 0.45–0.75
const VERY_SHORT_DAMPEN = 0.35;          // tune: 0.25–0.55

// Signal stacking
const MIN_INTENT_SIGNALS_TO_ESCALATE = 2; // must be >=2 to label suspicious
const HARD_OVERRIDE_PROB = 0.995;         // extremely high confidence override

export function scoreEmail(
  fused: FusedSignals,
  bodyTextLen?: number,
  binaryProb?: number
): { score: number; risk: RiskLabel; confidence: ConfidenceBand } {
  let score = 0;

  // Strong signals
  if (fused.credHits.length) score += 35;
  if (fused.paymentHits.length) score += 25;
  if (fused.threatHits.length) score += 20;

  // Link-based risk
  score += Math.min(24, fused.bodyLinkCount * 6);
  if ((fused.linkFlags["DISPLAY_MISMATCH"] ?? 0) > 0) {
    const strongIntent = fused.credHits.length > 0 || fused.paymentHits.length > 0 || fused.threatHits.length > 0;
    const nlpHigh = (fused.nlp?.semanticSuspicion ?? 0) >= 0.75;
    score += strongIntent || nlpHigh ? 12 : 6;
  }
  if ((fused.linkFlags["PUNYCODE"] ?? 0) > 0) score += 20;
  if ((fused.linkFlags["SHORTENER"] ?? 0) > 0) score += 10;
  if ((fused.linkFlags["IP_HOST"] ?? 0) > 0) score += 15;
  if ((fused.linkFlags["MANY_SUBDOMAINS"] ?? 0) > 0) score += 8;
  if (fused.senderLinkMismatchPrimary) {
    const strongIntent = fused.credHits.length > 0 || fused.paymentHits.length > 0 || fused.threatHits.length > 0;
    const nlpHigh = (fused.nlp?.semanticSuspicion ?? 0) >= 0.75;
    score += strongIntent || nlpHigh ? 12 : 4;
  } else if (fused.senderLinkMismatch) {
    score += 3;
  }

  // Auth signals (Tier A best-effort)
  if (fused.auth?.available) {
    if (fused.auth.dmarc === "fail") score += 20;
    if (fused.auth.dkim === "fail") score += 12;
    if (fused.auth.spf === "fail") score += 10;
  }

  // Thread anomaly
  if (fused.thread?.nameSameAddressChanged) score += 10;

  // Medium signal
  score += Math.min(10, fused.urgencyHits.length * 5);

  // NLP-based signal
  score += Math.min(40, Math.round(fused.nlpPoints ?? 0));

  // Weak signals (avoid unfairness)
  if (fused.exclamCount >= 3) score += 3;
  if (fused.allCapsTokenCount >= 3) score += 3;
  if (fused.nonAsciiCount >= 10) score += 3;

  // --- Hotfix: Short-text dampening + signal stacking ---
  // Count distinct intent signals
  const intentSignalCount =
    (fused.credHits.length > 0 ? 1 : 0) +
    (fused.paymentHits.length > 0 ? 1 : 0) +
    (fused.threatHits.length > 0 ? 1 : 0);

  // Apply dampening if short text + low intent signals
  if (bodyTextLen !== undefined && binaryProb !== undefined) {
    // Hard override: extremely high confidence bypasses dampening
    if (binaryProb < HARD_OVERRIDE_PROB) {
      if (bodyTextLen <= VERY_SHORT_BODYLEN_MAX) {
        // Very short: aggressive dampening unless multiple signals
        if (intentSignalCount < MIN_INTENT_SIGNALS_TO_ESCALATE) {
          score = Math.round(score * VERY_SHORT_DAMPEN);
        }
      } else if (bodyTextLen <= SHORT_TEXT_BODYLEN_MAX) {
        // Short: moderate dampening unless multiple signals
        if (intentSignalCount < MIN_INTENT_SIGNALS_TO_ESCALATE) {
          score = Math.round(score * SHORT_TEXT_DAMPEN);
        }
      }
    }
  }

  score = Math.max(0, Math.min(100, score));

  // Confidence: based on independent strong cues
  const strongEvidenceCount =
    (fused.credHits.length ? 1 : 0) +
    (fused.paymentHits.length ? 1 : 0) +
    (fused.threatHits.length ? 1 : 0) +
    ((fused.linkFlags["DISPLAY_MISMATCH"] ?? 0) > 0 ? 1 : 0) +
    ((fused.linkFlags["PUNYCODE"] ?? 0) > 0 ? 1 : 0) +
    ((fused.linkFlags["IP_HOST"] ?? 0) > 0 ? 1 : 0) +
    (fused.senderLinkMismatchPrimary ? 1 : 0) +
    ((fused.nlp?.semanticSuspicion ?? 0) >= 0.85 ? 1 : 0) +
    (fused.auth?.dmarc === "fail" ? 1 : 0) +
    (fused.thread?.nameSameAddressChanged ? 1 : 0);

  let risk: RiskLabel = "low";
  // --- Hotfix: Signal stacking requirement for medium/high ---
  if (score >= 70 && strongEvidenceCount >= 2) {
    risk = "high";
  } else if (score >= 25 && (strongEvidenceCount >= 1 || intentSignalCount >= MIN_INTENT_SIGNALS_TO_ESCALATE)) {
    // Require either strong evidence OR multiple intent signals for medium
    risk = "medium";
  } else {
    risk = "low";
  }

  let confidence: ConfidenceBand = "low";
  if (strongEvidenceCount >= 3) confidence = "high";
  else if (strongEvidenceCount === 2) confidence = "medium";
  else if (score >= 70) confidence = "medium"; // single strong cue but high score

  return { score, risk, confidence };
}
