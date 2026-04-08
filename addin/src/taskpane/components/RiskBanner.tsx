import React from "react";
import type { ConfidenceBand, Reason, RiskLabel } from "../../shared/types";

const bannerStyles: Record<string, React.CSSProperties> = {
  high: {
    background: "#FEE2E2",
    borderLeft: "4px solid #DC2626",
    color: "#991B1B",
  },
  medium: {
    background: "#FEF3C7",
    borderLeft: "4px solid #D97706",
    color: "#92400E",
  },
  low: {
    background: "#F0FDF4",
    borderLeft: "4px solid #16A34A",
    color: "#166534",
  },
};

function ShieldXIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <line x1="9" y1="9" x2="15" y2="15" />
      <line x1="15" y1="9" x2="9" y2="15" />
    </svg>
  );
}

function WarningTriangleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function headline(risk: RiskLabel): string {
  if (risk === "high") return "High phishing risk detected";
  if (risk === "medium") return "Suspicious email — review carefully";
  if (risk === "low") return "No phishing signals detected";
  return "Analysis unavailable";
}

function subline(risk: RiskLabel, topReason?: Reason): string {
  if (risk === "low") return "This email passed all security checks";
  if (risk === "unknown") return "";
  return topReason?.title ?? "";
}

export default function RiskBanner(props: {
  risk: RiskLabel;
  score: number;
  confidence?: ConfidenceBand;
  showConfidence?: boolean;
  isLoading?: boolean;
  reasons?: Reason[];
}) {
  if (props.isLoading) {
    return (
      <div style={{
        padding: "12px 14px",
        borderRadius: 8,
        background: "#F3F4F6",
        border: "1px solid #E5E7EB",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="opg-spinner" aria-hidden="true" />
          <span style={{ fontSize: 13, color: "#6B7280" }}>Analyzing email...</span>
        </div>
        <div className="opg-pulse" style={{
          marginTop: 10,
          height: 10,
          borderRadius: 4,
          background: "#D1D5DB",
          width: "60%",
        }} />
      </div>
    );
  }

  if (props.risk === "unknown") {
    return (
      <div style={{
        padding: "12px 14px",
        borderRadius: 8,
        background: "#F3F4F6",
        border: "1px solid #E5E7EB",
        fontSize: 13,
        color: "#6B7280",
      }}>
        Analysis unavailable
      </div>
    );
  }

  const colorStyle = bannerStyles[props.risk] ?? bannerStyles.low;
  const topReason = props.reasons?.[0];

  return (
    <div
      role="alert"
      style={{
        ...colorStyle,
        padding: "12px 14px",
        borderRadius: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        {props.risk === "high" && <ShieldXIcon />}
        {props.risk === "medium" && <WarningTriangleIcon />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>
            {headline(props.risk)}
          </div>
          {subline(props.risk, topReason) && (
            <div style={{ fontSize: 12, marginTop: 3, opacity: 0.85 }}>
              {subline(props.risk, topReason)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
