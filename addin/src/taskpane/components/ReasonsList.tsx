import React from "react";
import type { Reason } from "../../shared/types";

type ReasonCategory = "intent" | "structural" | "auth" | "binary";

function getCategory(code: Reason["code"]): ReasonCategory {
  if (
    code === "NLP_INTENT_CREDENTIAL" ||
    code === "NLP_INTENT_PAYMENT" ||
    code === "NLP_INTENT_THREAT" ||
    code === "NLP_INTENT_IMPERSONATION" ||
    code === "CRED_REQUEST" ||
    code === "PAYMENT_REQUEST" ||
    code === "THREAT_LANGUAGE" ||
    code === "URGENCY_LANGUAGE" ||
    code === "SUSPICIOUS_COMBO" ||
    code === "STYLE_ANOMALY" ||
    code === "NON_ASCII"
  ) {
    return "intent";
  }
  if (
    code === "AUTH_DKIM_FAIL" ||
    code === "AUTH_SPF_FAIL" ||
    code === "AUTH_DMARC_FAIL" ||
    code === "AUTH_UNAVAILABLE" ||
    code === "THREAD_NAME_ADDRESS_CHANGE"
  ) {
    return "auth";
  }
  if (code === "BINARY_GATE_ALLOW" || code === "BINARY_GATE_BLOCK") {
    return "binary";
  }
  return "structural";
}

function strengthToConfidence(strength: Reason["strength"]): number {
  if (strength === "high") return 0.9;
  if (strength === "medium") return 0.6;
  return 0.3;
}

function barColor(confidence: number): string {
  if (confidence > 0.75) return "#DC2626";
  if (confidence > 0.5) return "#D97706";
  return "#9CA3AF";
}

function IntentIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2a10 10 0 1 0 10 10" />
      <path d="M12 8v4l3 3" />
      <path d="M18 2l4 4-4 4" />
    </svg>
  );
}

function StructuralIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}

function AuthIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <polyline points="9 12 11 14 15 10" />
    </svg>
  );
}

function BinaryIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function CategoryIcon({ category }: { category: ReasonCategory }) {
  if (category === "intent") return <IntentIcon />;
  if (category === "structural") return <StructuralIcon />;
  if (category === "auth") return <AuthIcon />;
  return <BinaryIcon />;
}

export default function ReasonsList(props: { reasons: Reason[] }) {
  if (!props.reasons?.length) return null;

  return (
    <div>
      <div style={{
        fontSize: 11,
        fontVariant: "small-caps",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        color: "#9CA3AF",
        marginBottom: 8,
      }}>
        Why this was flagged:
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {props.reasons.map((r, i) => {
          const category = getCategory(r.code);
          const confidence = strengthToConfidence(r.strength);
          return (
            <div key={`${r.code}-${i}`} style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 8,
              padding: "4px 0",
            }}>
              <span style={{ color: "#6B7280", flexShrink: 0, marginTop: 2 }}>
                <CategoryIcon category={category} />
              </span>
              <span style={{
                fontSize: 12,
                color: "#1F2937",
                flex: 1,
                minWidth: 0,
                wordBreak: "break-word",
                whiteSpace: "normal",
                overflow: "visible",
                lineHeight: 1.4,
              }}>
                {r.title}
              </span>
              <div style={{
                width: 80,
                flexShrink: 0,
                alignSelf: "center",
              }}>
                <div style={{
                  height: 4,
                  borderRadius: 2,
                  background: "#E5E7EB",
                  overflow: "hidden",
                }}>
                  <div style={{
                    height: "100%",
                    width: `${confidence * 100}%`,
                    background: barColor(confidence),
                    borderRadius: 2,
                  }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
