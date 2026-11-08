import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

const api = process.env.TADKA_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@shared": path.resolve(__dirname, "../../packages/shared/types"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: api, changeOrigin: true },
      "/ws": { target: api.replace("http", "ws"), ws: true },
    },
  },
  // The Vosk speech engine (WASM) is one large chunk, loaded only when an offline-speech call starts.
  build: { target: "es2022", chunkSizeWarningLimit: 6000 },
  test: { environment: "node" },
});
