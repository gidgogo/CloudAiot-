/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 서버(5173)는 /api, /ws, /health를 FastAPI(기본 8000)로 넘긴다.
// 브라우저 입장에서는 같은 출처라 Cookie·CSRF가 운영(Nginx)과 같은 방식으로 동작한다.
const apiTarget = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";
const proxy = {
  "/api": { target: apiTarget },
  "/health": { target: apiTarget },
  "/ws": { target: apiTarget.replace(/^http/, "ws"), ws: true },
};

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
