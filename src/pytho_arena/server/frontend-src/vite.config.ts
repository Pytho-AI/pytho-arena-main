import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/static/",
  plugins: [
    react(),
    {
      name: "strip-output-trailing-whitespace",
      generateBundle(_options, bundle) {
        Object.values(bundle).forEach((output) => {
          if (output.type === "chunk") output.code = output.code.replace(/[ \t]+$/gm, "");
        });
      },
    },
  ],
  build: {
    outDir: "../frontend",
    emptyOutDir: true,
    assetsInlineLimit: 0,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: (assetInfo) =>
          assetInfo.names?.some((name) => name.endsWith(".css"))
            ? "styles.css"
            : "assets/[name]-[hash][extname]",
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8096",
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
