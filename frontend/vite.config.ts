import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxy = {
    "/article-api": {
      target: env.ARTICLE_API_PROXY_TARGET || "http://127.0.0.1:8010",
      changeOrigin: true,
      rewrite: (path: string) => path.replace(/^\/article-api/, "/api"),
    },
    "/api": {
      target: env.API_PROXY_TARGET || "http://127.0.0.1:8000",
      changeOrigin: true,
    },
  };
  return {
    plugins: [react()],
    server: { port: 5173, strictPort: true, proxy },
    preview: { port: 4173, strictPort: true, proxy },
  };
});
