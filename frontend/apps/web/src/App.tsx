import { useEffect, useState } from "react"
import { LandingPage } from "@/pages/LandingPage"
import { LoginPage } from "@/pages/LoginPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { getCurrentUser, signOut } from "@/api/auth"
import { isLocalMode } from "@/config/mode"
import {
  type PageId,
  PAGE_ROUTES,
  resolvePageFromHash,
  getRedirectForPage,
} from "@/config/routes"

function setWindowHash(hash: string): void {
  if (typeof window !== "undefined") {
    window.location.assign(hash)
  }
}

export function App() {
  const isLocal = isLocalMode()
  const [isAuthenticated, setIsAuthenticated] = useState(() => isLocal)
  const [isCheckingAuth, setIsCheckingAuth] = useState(() => !isLocal)
  const [currentPage, setCurrentPage] = useState<PageId>(() => {
    if (typeof window !== "undefined") {
      return resolvePageFromHash(window.location.hash, isLocal)
    }
    return "landing"
  })

  // Synchronize authentication in Cloud Mode
  useEffect(() => {
    if (!isLocal) {
      void getCurrentUser().then((user) => {
        setIsAuthenticated(Boolean(user))
        setIsCheckingAuth(false)
      })
    }

    const handleHashChange = () => {
      const targetPage = resolvePageFromHash(window.location.hash, isLocal)
      setCurrentPage(targetPage)
    }

    window.addEventListener("hashchange", handleHashChange)
    return () => window.removeEventListener("hashchange", handleHashChange)
  }, [isLocal])

  const navigateTo = (pageId: PageId) => {
    const redirect = getRedirectForPage(pageId, isAuthenticated, isLocal)
    const target = redirect ?? pageId
    setCurrentPage(target)
    setWindowHash(PAGE_ROUTES[target].defaultHash)
    window.scrollTo({ top: 0, behavior: "instant" })
  }

  const handleSignOut = async () => {
    if (isLocal) {
      navigateTo("landing")
      return
    }
    await signOut()
    setIsAuthenticated(false)
    navigateTo("login")
  }

  if (isCheckingAuth) {
    return <div className="min-h-screen bg-paper" />
  }

  // Enforce access control across all pages using the route map
  const activePage =
    getRedirectForPage(currentPage, isAuthenticated, isLocal) ?? currentPage

  if (activePage === "dashboard") {
    return (
      <DashboardPage
        onNavigateLanding={() => navigateTo("landing")}
        onSignOut={() => void handleSignOut()}
      />
    )
  }

  if (activePage === "login") {
    return (
      <LoginPage
        onNavigateLanding={() => navigateTo("landing")}
        onNavigateDashboard={() => {
          setIsAuthenticated(true)
          navigateTo("dashboard")
        }}
      />
    )
  }

  return (
    <LandingPage
      onNavigateLogin={() => navigateTo("login")}
      onNavigateDashboard={() => navigateTo("dashboard")}
    />
  )
}
