import React from "react";
import ReactDOM from "react-dom/client";

import { AppErrorBoundary } from "@/components/cockpit/AppErrorBoundary";
import App from "./App";
import "./index.css";
import "./styles/cockpit.css";
import "./styles/onboarding.css";
import "./styles/birthPhase.css";
import "./styles/birthWizard.css";
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </React.StrictMode>,
);
