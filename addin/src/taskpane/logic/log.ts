import type { AnalysisResult, Condition } from "../../shared/types";

export type UserAction = "ANALYZE" | "VIEW_REASONS" | "INSPECT_LINKS" | "REPORT_PHISH" | "MARK_SAFE" | "DISMISS";

type LogEvent = {
  ts: string;
  action: UserAction;
  condition: Condition;
  hashedMessageId?: string;
  score?: number;
  risk?: string;
  confidence?: string;
  reasonCodes?: string[];
  linkDomains?: string[];
};

const STORAGE_KEY = "opg_logs_v1";

export function appendLog(evt: LogEvent) {
  try {
    const existing = localStorage.getItem(STORAGE_KEY);
    const arr: LogEvent[] = existing ? JSON.parse(existing) : [];
    arr.push(evt);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
  } catch {
    // ignore
  }
  // eslint-disable-next-line no-console
  console.log("[OPG]", evt);
}

export function exportLogs(): string {
  const existing = localStorage.getItem(STORAGE_KEY);
  return existing || "[]";
}

export function clearLogs() {
  localStorage.removeItem(STORAGE_KEY);
}

export function logAnalysis(action: UserAction, result: AnalysisResult, hashedMessageId?: string) {
  appendLog({
    ts: new Date().toISOString(),
    action,
    condition: result.condition,
    hashedMessageId,
    score: result.score,
    risk: result.risk,
    confidence: result.confidence,
    reasonCodes: result.reasons.map((r) => r.code),
    linkDomains: Array.from(new Set(result.links.map((l) => l.domain)))
  });
}
