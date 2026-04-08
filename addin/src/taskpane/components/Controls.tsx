import React from "react";
import type { Condition } from "../../shared/types";

export default function Controls(props: {
  condition: Condition;
  onAnalyze: () => void;
  onToggleDetails: () => void;
  onToggleLinks: () => void;
  onReport: () => void;
  onMarkSafe: () => void;
  onDismiss: () => void;
  onExportLogs: () => void;
  onClearLogs: () => void;
  isAnalyzing: boolean;
  // disableAnalyze: boolean;

}) {
  return (
    <div className="opg-card">
      <div className="opg-row" style={{ justifyContent: "space-between" }}>
        <div>
          <div style={{ fontWeight: 700 }}>Controls</div>
          <div className="opg-muted" style={{ marginTop: 2 }}>
            Condition: <span className="opg-pill">{props.condition}</span>
          </div>
        </div>
      </div>

      <div className="opg-row" style={{ marginTop: 10 }}>
        <button className="opg-btn" onClick={props.onAnalyze} disabled={props.isAnalyzing}>
          {props.isAnalyzing ? "Analyzing…" : "Analyze"}
        </button>

        <button className="opg-btn secondary" onClick={props.onToggleDetails}>
          View reasons
        </button>

        <button className="opg-btn secondary" onClick={props.onToggleLinks}>
          Inspect links
        </button>
      </div>

      <div className="opg-row" style={{ marginTop: 10 }}>
        <button className="opg-btn" onClick={props.onReport}>
          Report phishing
        </button>
        <button className="opg-btn secondary" onClick={props.onMarkSafe}>
          Mark safe
        </button>
        <button className="opg-btn secondary" onClick={props.onDismiss}>
          Dismiss
        </button>
      </div>

      <div className="opg-row" style={{ marginTop: 10 }}>
        <button className="opg-btn secondary" onClick={props.onExportLogs}>
          Export logs
        </button>
        <button className="opg-btn secondary" onClick={props.onClearLogs}>
          Clear logs
        </button>
      </div>
    </div>
  );
}
