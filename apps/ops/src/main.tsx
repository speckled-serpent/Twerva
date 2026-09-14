import { StrictMode, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";

import { App } from "./App";

import "./index.css";

const rootElement: HTMLElement | null = document.getElementById("root");

if (rootElement === null) {
  throw new Error("Root element with id 'root' was not found in index.html.");
}

const reactRoot: Root = createRoot(rootElement);
const applicationElement: ReactElement = (
  <StrictMode>
    <App />
  </StrictMode>
);

reactRoot.render(applicationElement);
