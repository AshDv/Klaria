import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy des appels /api vers le backend FastAPI (port 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: { "/api": "http://localhost:8000" },
  },
});
