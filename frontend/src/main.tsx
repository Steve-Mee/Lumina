import React from "react";
import ReactDOM from "react-dom/client";
import { syncDevApiKeyFromEnv } from "./bootstrap/syncDevApiKeyFromEnv";
import App from "./App";
import "./index.css";

syncDevApiKeyFromEnv();

const rootEl = document.getElementById("root");

if (!rootEl) {
  throw new Error('Root element with id "root" not found.');
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
