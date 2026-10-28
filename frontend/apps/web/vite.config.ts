import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const rootDir = resolve(import.meta.dirname, "../../..")
  // Load environment variables from the repo root and apps/web
  const rootEnv = loadEnv(mode, rootDir, ["RUN_LOCAL", "VITE_", "CODEMAP_"])
  const localEnv = loadEnv(mode, import.meta.dirname, [
    "RUN_LOCAL",
    "VITE_",
    "CODEMAP_",
  ])
  const env = { ...rootEnv, ...localEnv }

  const isLocal =
    env.RUN_LOCAL === "true" ||
    env.RUN_LOCAL === "1" ||
    env.VITE_RUN_LOCAL === "true" ||
    env.CODEMAP_MODE === "local" ||
    env.VITE_CODEMAP_MODE === "local"

  return {
    plugins: [react(), tailwindcss()],
    define: {
      __RUN_LOCAL__: JSON.stringify(isLocal),
      "import.meta.env.RUN_LOCAL": JSON.stringify(isLocal ? "true" : "false"),
      "import.meta.env.VITE_CODEMAP_MODE": JSON.stringify(
        isLocal ? "local" : "cloud"
      ),
    },
    server: {
      proxy: {
        "/api": "http://localhost:8000",
      },
    },
    resolve: {
      alias: {
        "@": resolve(import.meta.dirname, "./src"),
      },
    },
  }
})
