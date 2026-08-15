import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { DataProvider } from "./DataContext";
import { LocaleProvider } from "./LocaleContext";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <DataProvider>
      <LocaleProvider>
        <App />
      </LocaleProvider>
    </DataProvider>
  </StrictMode>,
);
