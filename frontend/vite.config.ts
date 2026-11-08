import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const bridge = "http://127.0.0.1:8756";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: bridge, changeOrigin: false },
      "/ws": { target: bridge.replace("http", "ws"), ws: true, changeOrigin: false },
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
    proxy: {
      "/api": { target: bridge, changeOrigin: false },
      "/ws": { target: bridge.replace("http", "ws"), ws: true, changeOrigin: false },
    },
  },
  build: {
    target: "es2020",
    sourcemap: false,
  },
});
