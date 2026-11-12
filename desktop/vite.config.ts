import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Electron 加载 file:// 时资源必须用相对路径
export default defineConfig({
  plugins: [react()],
  base: "./",
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: { port: 5174, strictPort: true },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
  },
});
