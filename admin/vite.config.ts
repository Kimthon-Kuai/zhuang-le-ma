import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

/** 去掉 Vite 注入的 crossorigin 属性：后台与 API 同源，不需要 CORS 预检 */
function stripCrossorigin(): Plugin {
  return {
    name: "strip-crossorigin",
    enforce: "post",
    transformIndexHtml(html) {
      return html.replace(/\s+crossorigin/g, "");
    },
  };
}

// 后台由服务端挂在 /admin 下，所以资源用相对路径
export default defineConfig({
  plugins: [react(), stripCrossorigin()],
  base: "./",
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5175,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8017" },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    modulePreload: { polyfill: false },
  },
});
