import React from "react";
import type { ExtractedLink } from "../../shared/types";

export default function LinkInspector(props: { links: ExtractedLink[] }) {
  if (!props.links?.length) {
    return (
      <div className="opg-card">
        <strong>Links</strong>
        <div className="opg-muted" style={{ marginTop: 6 }}>
          No links found in the extracted body text.
        </div>
      </div>
    );
  }

  return (
    <div className="opg-card">
      <strong>Links</strong>
      <table className="opg-table" style={{ marginTop: 8 }}>
        <thead>
          <tr>
            <th>Domain</th>
            <th>Flags</th>
            <th>Destination</th>
          </tr>
        </thead>
        <tbody>
          {props.links.map((l, idx) => (
            <tr key={`${l.domain}-${idx}`}>
              <td style={{ fontWeight: 700 }}>{l.domain}</td>
              <td className="opg-muted">{l.flags.length ? l.flags.join(", ") : "—"}</td>
              <td className="opg-muted" style={{ maxWidth: 220, wordBreak: "break-word" }}>
                {l.href}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="opg-muted" style={{ marginTop: 8, fontSize: 12 }}>
        Tip: If the displayed text differs from the destination domain, treat it as high risk.
      </div>
    </div>
  );
}
