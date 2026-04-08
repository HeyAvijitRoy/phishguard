import type { ThreadSignals } from "../../shared/types";

const FROM_LINE = /from:\s*([^<\n]+)?<([^>\s]+)>/gi;
const ON_WROTE = /on\s+.+?,\s*([^<\n]+)?<([^>\s]+)>\s+wrote:/gi;

function domainFromEmail(addr: string): string | undefined {
  const m = addr.match(/@([a-z0-9.-]+\.[a-z]{2,})/i);
  return m?.[1]?.toLowerCase();
}

function normalizeName(name?: string): string {
  return (name || "").trim().toLowerCase();
}

function collectMatches(text: string, re: RegExp): Array<{ name: string; email: string }> {
  const out: Array<{ name: string; email: string }> = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const name = normalizeName(m[1] || "");
    const email = (m[2] || "").trim();
    if (!email || !name) continue;
    out.push({ name, email });
    if (out.length >= 20) break;
  }
  return out;
}

export function getThreadSignals(bodyText: string, fromName?: string, fromEmail?: string): ThreadSignals {
  if (!bodyText) return { nameSameAddressChanged: false };

  const matches = [
    ...collectMatches(bodyText, FROM_LINE),
    ...collectMatches(bodyText, ON_WROTE)
  ];

  if (fromName && fromEmail) {
    matches.push({ name: normalizeName(fromName), email: fromEmail });
  }

  const nameToDomains = new Map<string, Set<string>>();
  for (const m of matches) {
    const domain = domainFromEmail(m.email);
    if (!domain) continue;
    if (!nameToDomains.has(m.name)) nameToDomains.set(m.name, new Set());
    nameToDomains.get(m.name)!.add(domain);
  }

  const evidence: string[] = [];
  let changed = false;
  for (const [name, domains] of Array.from(nameToDomains.entries())) {
    if (domains.size >= 2) {
      changed = true;
      evidence.push(`${name}: ${Array.from(domains).slice(0, 3).join(", ")}`);
    }
  }

  return {
    nameSameAddressChanged: changed,
    evidence: evidence.length ? evidence : undefined
  };
}
