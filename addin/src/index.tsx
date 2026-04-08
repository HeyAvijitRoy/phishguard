import React from "react";
import { createRoot } from "react-dom/client";
import Taskpane from "./taskpane/Taskpane";

const el = document.getElementById("root");
if (el) {
  createRoot(el).render(<Taskpane />);
}
