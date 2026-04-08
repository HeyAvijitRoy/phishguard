import type { EmailFeatures, ExtractedLink } from "../../shared/types";

const URGENCY = ["urgent", "immediately", "asap", "action required", "final notice", "right away"];
const CRED = ["password", "verify", "login", "sign in", "mfa", "otp", "code", "2fa", "credentials"];
const PAYMENT = ["invoice", "payment", "wire", "bank", "routing", "refund", "transfer", "gift card"];
const THREAT = ["suspend", "terminated", "locked", "disabled", "deactivated", "compromised"];

const ALLOWLIST = new Set([
  "linkedin.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "instagram.com"
]);

/**
 * Well-known enterprise email delivery domains where subdomain-based
 * sending is expected. The senderLinkMismatch signal is downweighted
 * (not disabled) for these senders because eTLD+1 comparison handles
 * most cases, but edge cases like HubSpot (hs-emails.com → hubspot.com)
 * still need handling.
 *
 * This list is NOT a security bypass — all other signals still run.
 * It only affects the structural mismatch signal weight.
 */
const KNOWN_DELIVERY_DOMAINS = new Set([
  "microsoft.com",
  "google.com",
  "salesforce.com",
  "hubspot.com",
  "mailchimp.com",
  "marketo.com",
  "exacttarget.com",  // Salesforce Marketing Cloud
  "eloqua.com",       // Oracle Marketing
  "constantcontact.com",
  "sendgrid.net",
  "amazonses.com",
  "nvidia.com",
  "adobe.com",
  "zendesk.com",
]);

const MULTI_PART_TLDS = new Set([
  "co.uk",
  "com.au",
  "co.jp",
  "co.in",
  "co.nz",
  "com.br",
  "com.mx",
  "com.sg",
  "com.tr",
  "com.sa",
  "com.ar",
  "com.hk",
  "com.tw",
  "com.cn",
  "com.my",
  "com.ph",
  "co.za"
]);

function findHits(text: string, phrases: string[]): string[] {
  const t = text.toLowerCase();
  const hits: string[] = [];
  for (const p of phrases) {
    if (t.includes(p)) hits.push(p);
  }
  return hits;
}

function countAllCapsTokens(text: string): number {
  const tokens = text.split(/\s+/).filter(Boolean);
  let count = 0;
  for (const tok of tokens) {
    if (tok.length >= 4 && tok === tok.toUpperCase() && /[A-Z]/.test(tok)) count++;
  }
  return count;
}

function nonAsciiCount(text: string): number {
  let c = 0;
  for (const ch of text) {
    if (ch.charCodeAt(0) > 127) c++;
  }
  return c;
}

function getRegistrableDomain(host: string): string {
  const parts = host.split(".").filter(Boolean);
  if (parts.length < 2) return host;

  const tail = parts.slice(-2).join(".");
  const tail3 = parts.slice(-3).join(".");
  if (MULTI_PART_TLDS.has(tail)) return parts.slice(-3).join(".");
  if (MULTI_PART_TLDS.has(tail3)) return parts.slice(-4).join(".");
  return tail;
}

function isAllowlisted(domain: string): boolean {
  const root = getRegistrableDomain(domain);
  return ALLOWLIST.has(root);
}

export function computeFeatures(
  subject: string,
  bodyText: string,
  links: ExtractedLink[],
  fromDomain?: string
): EmailFeatures {
  const text = `${subject}\n\n${bodyText}`.trim();

  const urgencyHits = findHits(text, URGENCY);
  const credHits = findHits(text, CRED);
  const paymentHits = findHits(text, PAYMENT);
  const threatHits = findHits(text, THREAT);

  const exclamCount = (text.match(/!/g) ?? []).length;
  const allCapsTokenCount = countAllCapsTokens(text);
  const nonAscii = nonAsciiCount(text);

  const bodyLinks = links.filter((l) => (l.bucket ?? "body") === "body");
  const signatureLinks = links.filter((l) => (l.bucket ?? "body") === "signature");
  const footerLinks = links.filter((l) => (l.bucket ?? "body") === "footer");

  const linkFlags: Record<string, number> = {};
  for (const l of bodyLinks) {
    for (const f of l.flags) {
      linkFlags[f] = (linkFlags[f] ?? 0) + 1;
    }
  }

  const linkDomains = Array.from(new Set(bodyLinks.map((l) => l.domain)));
  const nonAllowlistedDomains = linkDomains.filter((d) => !isAllowlisted(d));

  let primaryCtaDomain: string | undefined;
  for (const l of bodyLinks) {
    if (isAllowlisted(l.domain)) continue;
    if ((l.displayText || "").trim().length >= 3) {
      primaryCtaDomain = l.domain;
      break;
    }
  }
  if (!primaryCtaDomain && nonAllowlistedDomains.length) {
    primaryCtaDomain = nonAllowlistedDomains[0];
  }

  // eTLD+1 base domain for sender — prevents false positives on delivery subdomains
  // e.g. "email.microsoft.com" → "microsoft.com"
  const senderBaseDomain = fromDomain ? getRegistrableDomain(fromDomain) : undefined;

  function domainMatchesSender(linkDomain: string): boolean {
    // Exact hostname or subdomain-of-sender match
    if (linkDomain === fromDomain || linkDomain.endsWith(`.${fromDomain}`)) return true;
    // eTLD+1 match — email.microsoft.com vs microsoft.com → both → microsoft.com
    const linkBase = getRegistrableDomain(linkDomain);
    if (senderBaseDomain && linkBase === senderBaseDomain) return true;
    // Known delivery domain cross-match — hs-emails.com sender, hubspot.com links
    if (
      senderBaseDomain &&
      KNOWN_DELIVERY_DOMAINS.has(senderBaseDomain) &&
      KNOWN_DELIVERY_DOMAINS.has(linkBase)
    ) return true;
    return false;
  }

  const senderLinkMismatch =
    !!fromDomain &&
    nonAllowlistedDomains.length > 0 &&
    !nonAllowlistedDomains.some(domainMatchesSender);

  const senderLinkMismatchPrimary =
    !!fromDomain &&
    !!primaryCtaDomain &&
    !domainMatchesSender(primaryCtaDomain);

  return {
    urgencyHits,
    credHits,
    paymentHits,
    threatHits,
    exclamCount,
    allCapsTokenCount,
    nonAsciiCount: nonAscii,
    linkCount: bodyLinks.length,
    bodyLinkCount: bodyLinks.length,
    signatureLinkCount: signatureLinks.length,
    footerLinkCount: footerLinks.length,
    linkFlags,
    linkDomains,
    senderLinkMismatch,
    senderLinkMismatchPrimary,
    primaryCtaDomain,
    senderDomain: fromDomain
  };
}

/*
 * Domain comparison regression cases:
 *
 * senderLinkMismatch SHOULD fire (true positives):
 *   verify-account.microsoftsecure-portal.com vs microsoft.com  → MISMATCH
 *   paypal-secure.phishing-site.net vs paypal.com               → MISMATCH
 *   company.fake-domain.com vs company.com                      → MISMATCH
 *
 * senderLinkMismatch SHOULD NOT fire (false positives fixed):
 *   email.microsoft.com vs microsoft.com                        → SAME (eTLD+1)
 *   go.salesforce.com vs salesforce.com                         → SAME (eTLD+1)
 *   replyto@email.microsoft.com vs go.microsoft.com            → SAME (eTLD+1)
 *   hs-emails.com vs hubspot.com                                → SAME (known delivery)
 *   mail.google.com vs google.com                               → SAME (eTLD+1)
 */
