export type PageId = "landing" | "login" | "dashboard"

export interface PageRouteConfig {
  id: PageId
  title: string
  /**
   * Hashes that correspond to this page (case-insensitive matching).
   */
  hashes: string[]
  /**
   * Whether this page requires user authentication when running in cloud mode.
   * In local mode (`RUN_LOCAL=true`), authentication is bypassed for ALL protected pages.
   */
  requiresAuth: boolean
  /**
   * Mode availability:
   * - "both": accessible in both local and cloud modes
   * - "cloud-only": accessible only in cloud mode (e.g. login/register)
   * - "local-only": accessible only in local mode
   */
  availability: "both" | "cloud-only" | "local-only"
  /**
   * Default window.location.hash for this page
   */
  defaultHash: string
}

/**
 * Single source of truth map of all pages in CodeMap.
 * Add new pages here to define their authentication requirements and mode availability.
 */
export const PAGE_ROUTES: Record<PageId, PageRouteConfig> = {
  landing: {
    id: "landing",
    title: "CodeMap — Understand Any Codebase",
    hashes: [
      "",
      "#",
      "#/",
      "#/landing",
      "#landing",
      "#hero",
      "#architecture",
      "#features",
      "#modes",
      "#docs",
      "#analyze",
      "#privacy-bar",
    ],
    requiresAuth: false,
    availability: "both",
    defaultHash: "#hero",
  },
  login: {
    id: "login",
    title: "CodeMap — Sign In",
    hashes: ["#signin", "#/login", "#login", "#register", "#signup"],
    requiresAuth: false,
    availability: "cloud-only",
    defaultHash: "#signin",
  },
  dashboard: {
    id: "dashboard",
    title: "CodeMap — Workspace & Projects",
    hashes: [
      "#dashboard",
      "#/dashboard",
      "#projects",
      "#/projects",
      "#workspace",
    ],
    requiresAuth: true,
    availability: "both",
    defaultHash: "#dashboard",
  },
}

/**
 * Array of all page IDs that require authentication in Cloud Mode.
 */
export const AUTHENTICATED_PAGES: PageId[] = Object.values(PAGE_ROUTES)
  .filter((route) => route.requiresAuth)
  .map((route) => route.id)

/**
 * Returns true if the page requires authentication.
 * In local mode (`isLocal = true`), authentication is universally disabled for ALL pages.
 */
export function isAuthRequired(pageId: PageId, isLocal: boolean): boolean {
  if (isLocal) {
    return false
  }
  return Boolean(PAGE_ROUTES[pageId]?.requiresAuth)
}

/**
 * Returns true if the given page is permitted in the current mode.
 * For example, login is "cloud-only" and forbidden in local mode.
 */
export function isPageAllowedInMode(pageId: PageId, isLocal: boolean): boolean {
  const config = PAGE_ROUTES[pageId]
  if (!config) return false

  if (isLocal && config.availability === "cloud-only") {
    return false
  }
  if (!isLocal && config.availability === "local-only") {
    return false
  }
  return true
}

/**
 * Matches a URL hash against the page map to determine the target page.
 */
export function resolvePageFromHash(rawHash: string, isLocal: boolean): PageId {
  const normalized = (rawHash || "").trim().toLowerCase()

  for (const route of Object.values(PAGE_ROUTES)) {
    if (route.hashes.includes(normalized)) {
      if (!isPageAllowedInMode(route.id, isLocal)) {
        return isLocal ? "dashboard" : "landing"
      }
      return route.id
    }
  }

  return "landing"
}

/**
 * Computes whether navigation to a page must be redirected based on authentication
 * and local/cloud mode rules.
 *
 * Returns the target PageId to redirect to, or null if access is allowed.
 */
export function getRedirectForPage(
  pageId: PageId,
  isAuthenticated: boolean,
  isLocal: boolean
): PageId | null {
  // 1. If page is not allowed in current mode (e.g. login in local mode) -> redirect
  if (!isPageAllowedInMode(pageId, isLocal)) {
    return isLocal ? "dashboard" : "landing"
  }

  // 2. If page requires auth and user is unauthenticated in cloud mode -> redirect to login
  if (isAuthRequired(pageId, isLocal) && !isAuthenticated) {
    return "login"
  }

  // 3. If user is already authenticated in cloud mode and visits login -> redirect to dashboard
  if (pageId === "login" && isAuthenticated && !isLocal) {
    return "dashboard"
  }

  return null
}
