declare const __RUN_LOCAL__: boolean | undefined

export type AppMode = "cloud" | "local"

/**
 * Returns true when running in strict offline / air-gapped local mode.
 * In local mode, all cloud dependencies (Supabase, user sign-in/sign-up,
 * remote sync) are bypassed and code is processed strictly locally.
 */
export function isLocalMode(): boolean {
  if (typeof __RUN_LOCAL__ !== "undefined") {
    return Boolean(__RUN_LOCAL__)
  }

  const envRunLocal =
    import.meta.env.RUN_LOCAL || import.meta.env.VITE_RUN_LOCAL
  if (envRunLocal === "true" || envRunLocal === "1") {
    return true
  }

  const envMode =
    import.meta.env.VITE_CODEMAP_MODE || import.meta.env.CODEMAP_MODE
  return envMode === "local"
}

export function isCloudMode(): boolean {
  return !isLocalMode()
}

export const APP_MODE: AppMode = isLocalMode() ? "local" : "cloud"
