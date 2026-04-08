import React, { useState } from "react";
import type { ExtractedLink, Reason, RiskLabel } from "../../shared/types";

const REASON_EXPLANATIONS: Record<string, string> = {
  CRED_REQUEST: "This email uses language commonly seen in requests for passwords, login details, or MFA codes.",
  NLP_INTENT_CREDENTIAL: "The overall meaning of this email matches credential-harvesting scams.",
  SUSPICIOUS_COMBO: "This email combines credential-request language with clickable links, which is a high-risk phishing pattern.",
  PAYMENT_REQUEST: "This email contains language associated with fraudulent payment requests.",
  NLP_INTENT_PAYMENT: "The overall meaning of this email matches payment redirection or financial fraud attempts.",
  THREAT_LANGUAGE: "This email threatens loss of access or other negative consequences to pressure you.",
  URGENCY_LANGUAGE: "This email uses urgent language to push you into acting quickly.",
  NLP_INTENT_THREAT: "The overall meaning of this email matches account threat or lockout scams.",
  NLP_INTENT_IMPERSONATION: "The sender may be impersonating a known contact or organization.",
  SENDER_LINK_MISMATCH: "The links in this email point to a different domain than the sender's address.",
  LINK_DISPLAY_MISMATCH: "A link appears to show one destination but actually points somewhere else.",
  LINK_PUNYCODE: "A link uses punycode, which can hide a lookalike domain.",
  LINK_SHORTENER: "A shortened link hides the true destination and makes inspection harder.",
  LINK_IP_HOST: "A link points directly to an IP address instead of a normal domain.",
  LINK_MANY_SUBDOMAINS: "A link uses an unusual number of subdomains, which can mimic trusted brands.",
  AUTH_DKIM_FAIL: "This email failed DKIM authentication, which can indicate spoofing.",
  AUTH_SPF_FAIL: "This email failed SPF authentication, which can indicate spoofing.",
  AUTH_DMARC_FAIL: "This email failed DMARC alignment, which is a strong spoofing signal.",
  AUTH_UNAVAILABLE: "Authentication results were not available for this message in the current mode.",
  THREAD_NAME_ADDRESS_CHANGE: "The sender identity in this reply chain does not match earlier messages.",
  STYLE_ANOMALY: "The writing style is unusual for a normal business email.",
  BINARY_GATE_ALLOW: "The phishing classifier found strong suspicious patterns in this email.",
  BINARY_GATE_BLOCK: "The phishing classifier found this email more consistent with benign mail.",
};

const DEFAULT_EXPLANATION = "Suspicious signal detected in this email.";

const btnBase: React.CSSProperties = {
  borderRadius: 6,
  padding: "6px 12px",
  fontSize: 13,
  cursor: "pointer",
  border: "1px solid #D1D5DB",
  background: "white",
  color: "#374151",
  transition: "filter 0.1s",
};

const btnDanger: React.CSSProperties = {
  borderRadius: 6,
  padding: "6px 12px",
  fontSize: 13,
  cursor: "pointer",
  border: "none",
  background: "#DC2626",
  color: "white",
  transition: "filter 0.1s",
};

function Btn(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { danger?: boolean }) {
  const { danger, style, ...rest } = props;
  const base = danger ? btnDanger : btnBase;
  return (
    <button
      {...rest}
      style={{ ...base, ...style }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.filter = "brightness(0.95)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.filter = "";
      }}
    />
  );
}

function truncate(s: string, max = 60): string {
  return s.length > max ? s.slice(0, max) + "..." : s;
}

export default function ActionButtons(props: {
  reasons: Reason[];
  links: ExtractedLink[];
  risk: RiskLabel;
}) {
  const [dismissed, setDismissed] = useState(false);
  const [showLearnWhy, setShowLearnWhy] = useState(false);
  const [showLinks, setShowLinks] = useState(false);
  const [reported, setReported] = useState(false);
  const explanations = Array.from(new Set(props.reasons.map((reason) => REASON_EXPLANATIONS[reason.code] ?? DEFAULT_EXPLANATION)));

  if (dismissed) return null;
  if (props.risk !== "medium" && props.risk !== "high") return null;

  return (
    <div>
      {/* Button row */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        <Btn onClick={() => setDismissed(true)}>Dismiss</Btn>
        <Btn
          onClick={() => {
            setShowLearnWhy((v) => !v);
            setShowLinks(false);
          }}
        >
          Learn why
        </Btn>
        <Btn
          onClick={() => {
            setShowLinks((v) => !v);
            setShowLearnWhy(false);
          }}
        >
          Inspect links
        </Btn>
        <Btn
          danger
          disabled={reported}
          style={reported ? { opacity: 0.6, cursor: "not-allowed" } : undefined}
          onClick={() => setReported(true)}
        >
          {reported ? "Reported" : "Report phishing"}
        </Btn>
      </div>

      {/* Report confirmation */}
      {reported && (
        <div style={{ marginTop: 8, fontSize: 12, color: "#16A34A" }}>
          Thank you for reporting. This helps improve detection.
        </div>
      )}

      {/* Learn Why panel */}
      {showLearnWhy && explanations.length > 0 && (
        <div style={{
          marginTop: 10,
          padding: "10px 12px",
          borderRadius: 8,
          background: "#F9FAFB",
          border: "1px solid #E5E7EB",
        }}>
          <div style={{ fontSize: 11, fontVariant: "small-caps", textTransform: "uppercase", letterSpacing: "0.05em", color: "#9CA3AF", marginBottom: 8 }}>
            Plain-English explanations:
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {explanations.map((explanation, i) => (
              <div key={`${explanation}-${i}`} style={{ fontSize: 12, color: "#374151" }}>
                <span style={{ color: "#6B7280" }}>- </span>
                {explanation}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Inspect Links panel */}
      {showLinks && (
        <div style={{
          marginTop: 10,
          padding: "10px 12px",
          borderRadius: 8,
          background: "#F9FAFB",
          border: "1px solid #E5E7EB",
        }}>
          <div style={{ fontSize: 11, fontVariant: "small-caps", textTransform: "uppercase", letterSpacing: "0.05em", color: "#9CA3AF", marginBottom: 8 }}>
            Links found in this email:
          </div>
          {props.links.length === 0 ? (
            <div style={{ fontSize: 12, color: "#9CA3AF" }}>No links found.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {props.links.map((l, i) => (
                <div
                  key={`${l.href}-${i}`}
                  title={l.href}
                  style={{ fontSize: 12, color: "#374151", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                >
                  {truncate(l.href)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
