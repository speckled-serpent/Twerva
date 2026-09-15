import react from "@vitejs/plugin-react";
import { defineConfig, type UserConfig } from "vite";

const localApiOrigin: string = "http://127.0.0.1:8000";

const viteConfiguration: UserConfig = defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: localApiOrigin,
        changeOrigin: true,
      },
      "/health": {
        target: localApiOrigin,
        changeOrigin: true,
      },
    },
  },
});

export default viteConfiguration;
