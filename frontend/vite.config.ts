import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/ws": { target: "http://localhost:8080", ws: true },
      "/session": "http://localhost:8080",
      "/health": "http://localhost:8080",
      "/voice": "http://localhost:8080",
      "/learnings": "http://localhost:8080",
    },
  },
});
