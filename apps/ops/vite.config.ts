import react from "@vitejs/plugin-react";
import { defineConfig, type UserConfig } from "vite";

const viteConfiguration: UserConfig = defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});

export default viteConfiguration;
