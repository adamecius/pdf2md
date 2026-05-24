import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("root element not found");
}

// Strip the trailing slash from Vite's BASE_URL — react-router treats
// "/pdf2md/" as the entire pathname and dispatches "/" routes correctly,
// but expects the basename to be normalised without trailing slash.
const basename = (import.meta.env.BASE_URL ?? "/").replace(/\/$/, "") || "/";

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
