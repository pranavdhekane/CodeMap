export type AppMode = "cloud" | "local"

// Default to cloud mode for landing & marketing, can be configured via environment or backend endpoint
export const APP_MODE: AppMode =
  (import.meta.env.VITE_CODEMAP_MODE as AppMode) || "cloud"

export function isLocalMode(): boolean {
  return APP_MODE === "local"
}

export function isCloudMode(): boolean {
  return APP_MODE === "cloud"
}
