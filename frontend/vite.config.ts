/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8080" } },
  // Testes de frontend (fase 3,5): vitest + jsdom, arquivos `*.test.ts(x)` ao lado do
  // que testam. `npm test` roda uma vez (CI); `npx vitest` fica observando.
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
