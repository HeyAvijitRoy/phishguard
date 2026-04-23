import React from "react";
import { createRoot } from "react-dom/client";
import Taskpane from "./taskpane/Taskpane";

const el = document.getElementById("root");
if (el) {
  try {
    createRoot(el).render(<Taskpane />);
  } catch (error) {
    // Surface startup failures inside the taskpane instead of failing silently.
    el.innerHTML = `
      <div style="padding:16px;font-family:Segoe UI,sans-serif;color:#111">
        <div style="font-size:16px;font-weight:700;margin-bottom:8px">PhishGuard failed to start</div>
        <div style="font-size:13px;color:#555;white-space:pre-wrap">${String(error)}</div>
      </div>
    `;
    // eslint-disable-next-line no-console
    console.error("Taskpane bootstrap failed", error);
  }
}
