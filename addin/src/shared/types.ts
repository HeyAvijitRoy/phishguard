export type Condition = "A_BASELINE" | "B_REASONS" | "C_REASONS_PLUS_CONFIDENCE";

export type ConfidenceBand = "low" | "medium" | "high";

export type RiskLabel = "low" | "medium" | "high" | "unknown";

export type Reason = {
  code:
    | "LINK_DISPLAY_MISMATCH"
    | "LINK_SHORTENER"
    | "LINK_PUNYCODE"
    | "LINK_IP_HOST"
    | "LINK_MANY_SUBDOMAINS"
    | "SENDER_LINK_MISMATCH"
    | "CRED_REQUEST"
    | "PAYMENT_REQUEST"
    | "THREAT_LANGUAGE"
    | "URGENCY_LANGUAGE"
    | "STYLE_ANOMALY"
    | "NON_ASCII"
    | "SUSPICIOUS_COMBO"
    | "NLP_INTENT_CREDENTIAL"
    | "NLP_INTENT_PAYMENT"
    | "NLP_INTENT_THREAT"
    | "NLP_INTENT_IMPERSONATION"
    | "BINARY_GATE_ALLOW"
    | "BINARY_GATE_BLOCK"
    | "AUTH_DKIM_FAIL"
    | "AUTH_SPF_FAIL"
    | "AUTH_DMARC_FAIL"
    | "AUTH_UNAVAILABLE"
    | "THREAD_NAME_ADDRESS_CHANGE";
  title: string;
  detail: string;
  strength: "low" | "medium" | "high";
  evidence?: string[];
};

export type ExtractedEmail = {
  messageId?: string; // Office itemId when available
  subject: string;
  bodyText: string;
  bodyHtml?: string;
  from?: string;
  fromName?: string;
  fromEmail?: string;
  fromDomain?: string;
  to?: string[];
  dateTime?: string;
  conversationId?: string;
  internetHeaders?: string;
};

export type ExtractedLink = {
  href: string;
  displayText?: string;
  domain: string;
  flags: string[];
  bucket?: "body" | "signature" | "footer";
};

export type EmailFeatures = {
  urgencyHits: string[];
  credHits: string[];
  paymentHits: string[];
  threatHits: string[];
  exclamCount: number;
  allCapsTokenCount: number;
  nonAsciiCount: number;

  linkCount: number;
  bodyLinkCount: number;
  signatureLinkCount: number;
  footerLinkCount: number;
  linkFlags: Record<string, number>;
  linkDomains: string[];
  senderLinkMismatch: boolean;
  senderLinkMismatchPrimary: boolean;
  primaryCtaDomain?: string;
  senderDomain?: string;
};

export type AuthSignals = {
  available: boolean;
  dkim?: "pass" | "fail" | "neutral" | "none" | "softfail" | "temperror" | "permerror" | "unknown";
  spf?: "pass" | "fail" | "neutral" | "none" | "softfail" | "temperror" | "permerror" | "unknown";
  dmarc?: "pass" | "fail" | "none" | "temperror" | "permerror" | "unknown";
};

export type ThreadSignals = {
  nameSameAddressChanged: boolean;
  evidence?: string[];
};

export type AnalysisResult = {
  condition: Condition;
  risk: RiskLabel;
  score: number; // 0-100
  confidence: ConfidenceBand;
  reasons: Reason[];
  links: ExtractedLink[];
};

export type NlpSignals = {
  intentCredential: number; // 0..1
  intentPayment: number;
  intentThreat: number;
  intentImpersonation: number;
  semanticSuspicion: number; // aggregate
  keyPhrases?: string[];     // optional (for explanations)
};

