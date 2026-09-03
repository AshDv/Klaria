import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "html"],
      include: ["src/api.js", "src/dateTime.js", "src/PlatformIcon.jsx"],
      thresholds: { lines: 80, functions: 80, statements: 80, branches: 70 },
    },
  },
});
