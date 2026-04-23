import React, { useEffect, useMemo, useState } from "react";
import "./styles/taskpane.css";

import RiskBanner from "./components/RiskBanner";
import ReasonsList from "./components/ReasonsList";
import ActionButtons from "./components/ActionButtons";
import LinkInspector from "./components/LinkInspector";
import Controls from "./components/Controls";

import type { AnalysisResult, Condition, ExtractedLink } from "../shared/types";
import { getCurrentEmail } from "./logic/extractEmail";
import { computeFeatures } from "./logic/features";
import { scoreEmail } from "./logic/score";
import { buildReasons } from "./logic/explain";
import { fuseSignals } from "./logic/fuse";
import { hashId } from "./logic/hash";
import { exportLogs, clearLogs, logAnalysis } from "./logic/log";
import { extractLinksFromHtml, extractLinksFromText } from "./logic/extractLinks";
import { getAuthSignals } from "./logic/auth";
import { getThreadSignals } from "./logic/thread";

function getConditionFromUrl(): Condition {
  const params = new URLSearchParams(window.location.search);
  const c = params.get("cond");
  if (c === "A") return "A_BASELINE";
  if (c === "B") return "B_REASONS";
  if (c === "C") return "C_REASONS_PLUS_CONFIDENCE";
  return "C_REASONS_PLUS_CONFIDENCE";
}

function isDebugMode(): boolean {
  return new URLSearchParams(window.location.search).get("debug") === "1";
}

const EMPTY: AnalysisResult = {
  condition: "C_REASONS_PLUS_CONFIDENCE",
  risk: "unknown",
  score: 0,
  confidence: "low",
  reasons: [],
  links: []
};

const PHISH_GATE_THRESHOLD = 0.90;

type AnalysisModules = {
  computeNlpSignals: (subject: string, bodyText: string) => Promise<any>;
  scoreBinaryPhish: (subject: string, bodyText: string) => Promise<number>;
};

let analysisModulesPromise: Promise<AnalysisModules> | null = null;

function loadAnalysisModules(): Promise<AnalysisModules> {
  if (!analysisModulesPromise) {
    analysisModulesPromise = Promise.all([
      import("./logic/nlp"),
      import("./logic/binary")
    ]).then(([nlp, binary]) => ({
      computeNlpSignals: nlp.computeNlpSignals,
      scoreBinaryPhish: binary.scoreBinaryPhish
    }));
  }

  return analysisModulesPromise;
}

export default function Taskpane() {
  const condition = useMemo(() => getConditionFromUrl(), []);
  const debugMode = useMemo(() => isDebugMode(), []);

  const [isOfficeReady, setOfficeReady] = useState(false);
  const [isAnalyzing, setAnalyzing] = useState(false);

  const [result, setResult] = useState<AnalysisResult>({ ...EMPTY, condition });
  const [showReasons, setShowReasons] = useState(false);
  const [showLinks, setShowLinks] = useState(false);
  const [debug, setDebug] = useState("");
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  useEffect(() => {
    // Safe guard: Office exists only inside the Outlook add-in frame.
    const w = window as any;

    if (!w.Office || typeof w.Office.onReady !== "function") {
      setOfficeReady(false);
      return;
    }

    w.Office.onReady(() => setOfficeReady(true));
  }, []);

  async function analyze() {
    setAnalyzing(true);
    setDebug("");
    setLatencyMs(null);

    // [PhishGuard Latency Instrumentation START]
    const t0 = performance.now();
    let didTriggerStage2 = false;
    let riskTier: AnalysisResult["risk"] = "unknown";
    // [PhishGuard Latency Instrumentation END]

    try {
      const w: any = window as any;

      const hasOffice = !!w.Office;
      const hasContext = !!w.Office?.context;
      const hasMailbox = !!w.Office?.context?.mailbox;
      const hasItem = !!w.Office?.context?.mailbox?.item;

      setDebug(
        [
          `hasOffice=${hasOffice}`,
          `hasContext=${hasContext}`,
          `hasMailbox=${hasMailbox}`,
          `hasItem=${hasItem}`,
          `host=${w.Office?.context?.host ?? "?"}`,
          `platform=${w.Office?.context?.platform ?? "?"}`
        ].join(" | ")
      );

      if (!hasItem) {
        setDebug((d) => d + "\nERROR: Office.context.mailbox.item is not available. Open an email (Message Read) and re-open the add-in.");
        return;
      }

      const email = await getCurrentEmail();
      setDebug((d) => d + `\nsubjectLen=${email.subject?.length ?? 0} | bodyLen=${email.bodyText?.length ?? 0}`);

      const links: ExtractedLink[] = email.bodyHtml ? extractLinksFromHtml(email.bodyHtml) : extractLinksFromText(email.bodyText);

      setDebug((d) => d + `\nlinksFound=${links.length}`);

      const { scoreBinaryPhish, computeNlpSignals } = await loadAnalysisModules();
      const pPhish = await scoreBinaryPhish(email.subject, email.bodyText);
      setDebug((d) => d + `\nphishProb=${pPhish.toFixed(4)} gate=${PHISH_GATE_THRESHOLD}`);

      if (pPhish < PHISH_GATE_THRESHOLD) {
        const computed: AnalysisResult = {
          condition,
          risk: "low",
          score: Math.round(pPhish * 15),
          confidence: "low",
          reasons: [
            {
              code: "BINARY_GATE_BLOCK",
              title: "Binary model: likely benign",
              detail: `Binary suspicion ${pPhish.toFixed(2)} below gate ${PHISH_GATE_THRESHOLD}.`,
              strength: "low"
            }
          ],
          links
        };
          
        riskTier = computed.risk; // For latency logging
        setResult(computed);

        const hashed = await hashId(email.messageId || "");
        logAnalysis("ANALYZE", computed, hashed);

        setDebug((d) => d + `\nDONE: gated score=${computed.score}`);
        return;
      }

      didTriggerStage2 = true; // For latency instrumentation
      const features = computeFeatures(email.subject, email.bodyText, links, email.fromDomain);
      const auth = getAuthSignals(email.internetHeaders);
      const thread = getThreadSignals(email.bodyText, email.fromName, email.fromEmail);
      const nlp = await computeNlpSignals(email.subject, email.bodyText);
      const fused = fuseSignals(features, nlp, auth, thread);

      const scored = scoreEmail(fused, email.bodyText.length, pPhish);
      const reasons = buildReasons(fused);
      reasons.unshift({
        code: "BINARY_GATE_ALLOW",
        title: "Binary model: suspicious",
        detail: `Binary suspicion ${pPhish.toFixed(2)} exceeds gate ${PHISH_GATE_THRESHOLD}.`,
        strength: pPhish >= 0.9 ? "high" : "medium"
      });

      const computed: AnalysisResult = {
        condition,
        risk: scored.risk,
        score: scored.score,
        confidence: scored.confidence,
        reasons,
        links
      };

      riskTier = computed.risk; // For latency logging
      setResult(computed);

      const hashed = await hashId(email.messageId || "");
      logAnalysis("ANALYZE", computed, hashed);

      setDebug((d) => d + `\nDONE: score=${computed.score} reasons=${computed.reasons.length}`);
    } catch (e: any) {
      setDebug((d) => d + `\nEXCEPTION: ${e?.message ?? String(e)}`);
      console.error(e);
    } finally {
      // [PhishGuard Latency Instrumentation START]
      const t1 = performance.now();
      console.log(
        `[PhishGuard Latency] ${(t1 - t0).toFixed(1)} ms | stage2_triggered: ${didTriggerStage2} | risk: ${riskTier}`
      );
      // [PhishGuard Latency Instrumentation END]

      setLatencyMs(Math.round(t1 - t0));
      setAnalyzing(false);
    }
  }

  useEffect(() => {
    if (!isOfficeReady) return;
    const w: any = window as any;
    if (!w.Office?.context?.mailbox?.addHandlerAsync) return;

    w.Office.context.mailbox.addHandlerAsync(
      w.Office.EventType.ItemChanged,
      () => {
        analyze();
      }
    );
  }, [isOfficeReady]);

  function onExportLogs() {
    const json = exportLogs();
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "opg_logs_v1.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function onClearLogs() {
    clearLogs();
    // eslint-disable-next-line no-alert
    alert("Logs cleared.");
  }

  const showConfidence = condition === "C_REASONS_PLUS_CONFIDENCE";
  const reasonsVisible = showReasons && condition !== "A_BASELINE";
  const linksVisible = showLinks && condition !== "A_BASELINE";
  const showPrimaryReasons = condition !== "A_BASELINE" && (result.risk === "medium" || result.risk === "high") && !isAnalyzing;
  const showActionButtons = (result.risk === "medium" || result.risk === "high") && !isAnalyzing;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", fontFamily: "inherit" }}>
      {/* Header - always visible */}
      <div style={{
        borderBottom: "1px solid #E5E7EB",
        padding: "0 12px",
        height: 48,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        flexShrink: 0,
      }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>PhishGuard</div>
        <div style={{ fontSize: 12, color: "#6B7280" }}>Email security analysis</div>
      </div>

      {/* Content area */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}>
        <RiskBanner
          risk={result.risk}
          score={result.score}
          confidence={result.confidence}
          showConfidence={showConfidence}
          isLoading={isAnalyzing}
          reasons={result.reasons}
        />

        {showPrimaryReasons ? <ReasonsList reasons={result.reasons} /> : null}

        {showActionButtons ? (
          <ActionButtons
            reasons={result.reasons}
            links={result.links}
            risk={result.risk}
          />
        ) : null}

        <Controls
          condition={condition}
          onAnalyze={analyze}
          onToggleDetails={() => {
            setShowReasons((v) => !v);
            logAnalysis("VIEW_REASONS", result);
          }}
          onToggleLinks={() => {
            setShowLinks((v) => !v);
            logAnalysis("INSPECT_LINKS", result);
          }}
          onReport={() => {
            logAnalysis("REPORT_PHISH", result);
            // eslint-disable-next-line no-alert
            alert("Logged: report phishing.");
          }}
          onMarkSafe={() => {
            logAnalysis("MARK_SAFE", result);
            // eslint-disable-next-line no-alert
            alert("Logged: mark safe.");
          }}
          onDismiss={() => {
            logAnalysis("DISMISS", result);
            setShowReasons(false);
            setShowLinks(false);
          }}
          onExportLogs={onExportLogs}
          onClearLogs={onClearLogs}
          isAnalyzing={isAnalyzing}
        />

        {reasonsVisible && !showPrimaryReasons ? <ReasonsList reasons={result.reasons} /> : null}
        {linksVisible ? <LinkInspector links={result.links} /> : null}

        {condition === "A_BASELINE" ? (
          <div className="opg-card">
            <strong>Baseline condition</strong>
            <div className="opg-muted" style={{ marginTop: 6 }}>
              This condition intentionally hides detailed reasons to measure the effect of explanations.
            </div>
          </div>
        ) : null}

        {debug ? (
          <div className="opg-card">
            <strong>Debug</strong>
            <pre className="opg-muted" style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>
              {debug}
            </pre>
          </div>
        ) : null}
      </div>

      {/* Debug latency bar - only when ?debug=1 and analysis has run */}
      {debugMode && latencyMs !== null && (
        <div style={{
          borderTop: "1px solid #E5E7EB",
          padding: "4px 12px",
          fontSize: 11,
          color: "#9CA3AF",
          background: "#F9FAFB",
          flexShrink: 0,
        }}>
          Total: {latencyMs}ms
        </div>
      )}
    </div>
  );
}
