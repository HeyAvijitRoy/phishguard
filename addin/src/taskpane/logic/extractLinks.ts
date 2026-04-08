import type { ExtractedLink } from "../../shared/types";

const SHORTENERS = new Set([
  "bit.ly",
  "tinyurl.com",
  "t.co",
  "goo.gl",
  "ow.ly",
  "buff.ly",
  "is.gd",
  "rebrand.ly",
  "cutt.ly",
  "lnkd.in"
]);

const SIGNATURE_MARKERS = [
  "-- ",
  "best regards",
  "sincerely",
  "thanks,",
  "thank you,",
  "sent from",
  "kind regards",
  "regards,"
];

const FOOTER_MARKERS = [
  "unsubscribe",
  "privacy policy",
  "view in browser",
  "manage preferences",
  "update preferences",
  "email preferences",
  "terms of service"
];

function safeUrl(u: string): URL | null {
  try {
    const trimmed = u.trim().replace(/[)\].,;]+$/g, "");
    return new URL(trimmed);
  } catch {
    return null;
  }
}

function getDomain(url: URL): string {
  return (url.hostname || "").toLowerCase();
}

function isIpHost(host: string): boolean {
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
}

function countSubdomains(host: string): number {
  const parts = host.split(".").filter(Boolean);
  return Math.max(0, parts.length - 2);
}

function detectFlags(url: URL, displayText?: string): string[] {
  const flags: string[] = [];
  const domain = getDomain(url);

  if (domain.startsWith("xn--")) flags.push("PUNYCODE");
  if (SHORTENERS.has(domain)) flags.push("SHORTENER");
  if (isIpHost(domain)) flags.push("IP_HOST");
  if (countSubdomains(domain) >= 3) flags.push("MANY_SUBDOMAINS");

  if (displayText) {
    const dt = displayText.trim().toLowerCase();
    // If display text contains a domain-like token that differs from href domain
    const m = dt.match(/([a-z0-9-]+\.)+[a-z]{2,}/i);
    if (m && m[0] && !domain.includes(m[0].toLowerCase())) {
      flags.push("DISPLAY_MISMATCH");
    }
  }

  return flags;
}

function findBoundaryIndex(text: string, markers: string[]): number | null {
  const lower = text.toLowerCase();
  let best: number | null = null;
  for (const marker of markers) {
    const idx = lower.indexOf(marker);
    if (idx >= 0 && (best === null || idx < best)) best = idx;
  }
  return best;
}

function isFooterLink(displayText: string, href: string): boolean {
  const t = `${displayText} ${href}`.toLowerCase();
  return FOOTER_MARKERS.some((m) => t.includes(m));
}

function classifyBucket(text: string, index: number, displayText: string, href: string): "body" | "signature" | "footer" {
  const sigIdx = findBoundaryIndex(text, SIGNATURE_MARKERS);
  const footIdx = findBoundaryIndex(text, FOOTER_MARKERS);

  if (isFooterLink(displayText, href)) return "footer";
  if (footIdx !== null && index >= footIdx) return "footer";
  if (sigIdx !== null && index >= sigIdx) return "signature";
  return "body";
}

export function extractLinksFromText(bodyText: string): ExtractedLink[] {
  if (!bodyText) return [];

  const matches = Array.from(bodyText.matchAll(/https?:\/\/[^\s<>"']+/g));
  const seen = new Set<string>();
  const links: ExtractedLink[] = [];

  for (const match of matches) {
    const raw = match[0];
    if (seen.has(raw)) continue;
    seen.add(raw);

    const url = safeUrl(raw);
    if (!url) continue;

    const domain = getDomain(url);
    const flags = detectFlags(url);
    const idx = match.index ?? 0;
    const bucket = classifyBucket(bodyText, idx, "", url.toString());

    links.push({ href: url.toString(), domain, flags, bucket });
  }

  return links;
}

export function extractLinksFromHtml(html: string): ExtractedLink[] {
  if (!html) return [];

  const doc = new DOMParser().parseFromString(html, "text/html");
  const anchors = Array.from(doc.querySelectorAll("a"));
  const out: ExtractedLink[] = [];
  const textContent = (doc.body?.textContent || "").trim();
  const lowerText = textContent.toLowerCase();

  for (const a of anchors) {
    const rawHref = (a.getAttribute("href") || "").trim();
    if (!rawHref) continue;

    // Ignore mailto, javascript, and fragment links
    if (/^(mailto:|javascript:|#)/i.test(rawHref)) continue;

    const url = safeUrl(rawHref);
    if (!url) continue;

    const displayText = (a.textContent || "").trim();
    const domain = getDomain(url);
    const flags = detectFlags(url, displayText);
    const token = displayText || url.toString();
    const idx = token ? lowerText.indexOf(token.toLowerCase()) : 0;
    const bucket = classifyBucket(textContent, idx >= 0 ? idx : 0, displayText, url.toString());

    out.push({ href: url.toString(), displayText, domain, flags, bucket });
  }

  // de-dupe by href
  const seen = new Set<string>();
  return out.filter((l) => (seen.has(l.href) ? false : (seen.add(l.href), true)));
}

