import type { AuthSignals } from "../../shared/types";

function pickResult(value?: string) {
  if (!value) return "unknown" as const;
  const v = value.toLowerCase();
  if (v.includes("pass")) return "pass" as const;
  if (v.includes("fail")) return "fail" as const;
  if (v.includes("softfail")) return "softfail" as const;
  if (v.includes("neutral")) return "neutral" as const;
  if (v.includes("none")) return "none" as const;
  if (v.includes("temperror")) return "temperror" as const;
  if (v.includes("permerror")) return "permerror" as const;
  return "unknown" as const;
}

function normalizeDmarc(value?: string) {
  const v = pickResult(value);
  if (v === "neutral" || v === "softfail") return "unknown" as const;
  return v;
}

function matchAuth(header: string, key: string): string | undefined {
  const re = new RegExp(`${key}\\s*=\\s*([^;\\s]+)`, "i");
  const m = header.match(re);
  return m?.[1];
}

export function getAuthSignals(headers?: string): AuthSignals {
  if (!headers) return { available: false };

  const lines = headers.split(/\r?\n/).filter(Boolean);
  const authLines = lines.filter((l) => /^authentication-results:/i.test(l));
  const spfLines = lines.filter((l) => /^received-spf:/i.test(l));

  const auth = authLines.join(" ");
  const spfLine = spfLines.join(" ");

  const dkimRaw = matchAuth(auth, "dkim");
  const dmarcRaw = matchAuth(auth, "dmarc");
  const spfRaw = matchAuth(auth, "spf") || spfLine.split(/[:;]/)[1];

  return {
    available: true,
    dkim: pickResult(dkimRaw),
    spf: pickResult(spfRaw),
    dmarc: normalizeDmarc(dmarcRaw)
  };
}
