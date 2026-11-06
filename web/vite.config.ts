import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const REPO_ROOT = ".."; // .env and design/tokens.css both live outside web/.

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, REPO_ROOT, "VITE_");

  return {
    envDir: REPO_ROOT,
    plugins: [react()],
    server: {
      fs: { allow: [REPO_ROOT] },
      // The browser always calls /api on its own origin. Vercel forwards it in production and
      // this proxy does in development, so the sign-in cookie is first-party and CORS isn't needed.
      proxy: { "/api": env.VITE_API_URL },
    },
  };
});
