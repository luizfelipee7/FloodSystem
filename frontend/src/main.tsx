import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";
import "./styles.css";
import App from "./App";
import { Experiments } from "./components/Experiments";

const experimentsEnabled = import.meta.env.VITE_EXPERIMENTS_ENABLED === "true" ||
  import.meta.env.VITE_ARTICLE_MODE === "true";
const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
const showExperiments = experimentsEnabled &&
  (currentPath === "/ensaios" || (import.meta.env.VITE_ARTICLE_MODE === "true" && currentPath === "/"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {showExperiments ? <Experiments /> : <App />}
  </StrictMode>,
);
