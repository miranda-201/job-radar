import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, Vite plays the role nginx plays in Docker: one origin, routed by path prefix.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api/scraper": "http://localhost:8000",
      "/api": "http://localhost:8080",
    },
  },
  test: {
    environment: "node",
  },
});
