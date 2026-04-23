import type { AuthSignals, EmailFeatures, NlpSignals, ThreadSignals } from "../../shared/types";

function nlpToPoints(nlp: NlpSignals): number {
  return (
    nlp.intentCredential * 30 +
    nlp.intentPayment * 25 +
    nlp.intentThreat * 15 +
    nlp.intentImpersonation * 10
  );
}

export function fuseSignals(features: EmailFeatures, nlp: NlpSignals, auth?: AuthSignals, thread?: ThreadSignals) {
  return {
    ...features,
    nlp,
    nlpPoints: nlpToPoints(nlp),
    auth,
    thread
  };
}

// ---------------------------------------------------------------------------
// Weighted fusion formula — S_final = α·S_bin + β·S_int + γ·S_struct + δ·S_meta
// ---------------------------------------------------------------------------

export const FUSION_WEIGHTS = {
  alpha: 0.50,  // S_bin   — binary gate probability (pPhish)
  beta:  0.30,  // S_int   — max intent probability from nlp
  gamma: 0.15,  // S_struct — structural signals normalized to [0,1]
  delta: 0.05,  // S_meta  — auth + thread signals normalized to [0,1]
} as const;

export const TIER_THRESHOLDS = {
  medium: 0.40,
  high:   0.70,
} as const;

// S_struct: features.ts returns EmailFeatures (raw counts/arrays/booleans, no numeric score).
// We replicate the structural portion of score.ts's weighting and normalize by MAX_STRUCT_SCORE=100.
// Structural contributions (matching score.ts):
//   credHits→35, paymentHits→25, threatHits→20, bodyLinks up to 24,
//   DISPLAY_MISMATCH→12, PUNYCODE→20, SHORTENER→10, IP_HOST→15,
//   MANY_SUBDOMAINS→8, senderLinkMismatchPrimary→12, urgencyHits up to 10
// MAX value before clamping ≈ 191 but cap at 100 to stay [0,1].
const MAX_STRUCT_SCORE = 100;

function normalizeStructural(features: EmailFeatures): number {
  let raw = 0;
  if (features.credHits.length > 0) raw += 35;
  if (features.paymentHits.length > 0) raw += 25;
  if (features.threatHits.length > 0) raw += 20;
  raw += Math.min(24, features.bodyLinkCount * 6);
  if ((features.linkFlags["DISPLAY_MISMATCH"] ?? 0) > 0) raw += 12;
  if ((features.linkFlags["PUNYCODE"] ?? 0) > 0) raw += 20;
  if ((features.linkFlags["SHORTENER"] ?? 0) > 0) raw += 10;
  if ((features.linkFlags["IP_HOST"] ?? 0) > 0) raw += 15;
  if ((features.linkFlags["MANY_SUBDOMAINS"] ?? 0) > 0) raw += 8;
  if (features.senderLinkMismatchPrimary) raw += 12;
  else if (features.senderLinkMismatch) raw += 3;
  raw += Math.min(10, features.urgencyHits.length * 5);
  return Math.min(1, raw / MAX_STRUCT_SCORE);
}

// S_meta: auth.ts returns { available, dkim?, spf?, dmarc? } with pass/fail/etc strings.
//         thread.ts returns { nameSameAddressChanged: boolean }.
// Weights match score.ts: dmarc_fail=20, dkim_fail=12, spf_fail=10, thread_changed=10 → sum=52.
const MAX_META_SCORE = 52;

function normalizeMeta(auth?: AuthSignals, thread?: ThreadSignals): number {
  let raw = 0;
  if (auth?.available) {
    if (auth.dmarc === "fail") raw += 20;
    if (auth.dkim === "fail") raw += 12;
    if (auth.spf === "fail") raw += 10;
  }
  if (thread?.nameSameAddressChanged) raw += 10;
  return Math.min(1, raw / MAX_META_SCORE);
}

function getS_int(nlp: NlpSignals): number {
  return Math.max(
    nlp.intentCredential,
    nlp.intentPayment,
    nlp.intentThreat,
    nlp.intentImpersonation
  );
}

export function computeS_final(
  S_bin: number,
  nlp: NlpSignals,
  features: EmailFeatures,
  auth?: AuthSignals,
  thread?: ThreadSignals
): { sScore: number; tier: "low" | "medium" | "high" } {
  const S_int    = getS_int(nlp);
  const S_struct = normalizeStructural(features);
  const S_meta   = normalizeMeta(auth, thread);

  const sScore =
    FUSION_WEIGHTS.alpha * S_bin +
    FUSION_WEIGHTS.beta  * S_int +
    FUSION_WEIGHTS.gamma * S_struct +
    FUSION_WEIGHTS.delta * S_meta;

  const tier: "low" | "medium" | "high" =
    sScore >= TIER_THRESHOLDS.high   ? "high"
  : sScore >= TIER_THRESHOLDS.medium ? "medium"
  : "low";

  return { sScore, tier };
}
