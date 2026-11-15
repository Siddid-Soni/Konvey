import { defineConfig } from "vite";

// the API runs on 8000; `npm run dev` proxies so the app is one origin in dev too
export default defineConfig({
  server: { port: 5173, proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } } },
});
