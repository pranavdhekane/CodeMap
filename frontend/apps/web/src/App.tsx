import { useEffect, useState } from "react"
import { LandingPage } from "@/pages/LandingPage"
import { LoginPage } from "@/pages/LoginPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { AnalysisPage } from "@/pages/AnalysisPage"
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

function getProjectIdFromHash(hash: string): string | null {
  try {
    const qIndex = hash.indexOf("?")
    if (qIndex !== -1) {
      const params = new URLSearchParams(hash.substring(qIndex))
      const paramVal = params.get("id") || params.get("project")
      if (paramVal) return paramVal
    }
    const match = hash.match(/#\/?analysis\/(\d+)/)
    if (match && match[1]) {
      return match[1]
    }
  } catch {
    // fallback
  }
  return null
}

export function App() {
  const isLocal = isLocalMode()
  const [isAuthenticated, setIsAuthenticated] = useState(() => isLocal)
  const [isCheckingAuth, setIsCheckingAuth] = useState(() => !isLocal)
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return getProjectIdFromHash(window.location.hash)
    }
    return null
  })
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
      const pId = getProjectIdFromHash(window.location.hash)
      if (pId) {
        setSelectedProjectId(pId)
      }
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

  const navigateToAnalysis = (projId?: string) => {
    if (projId) {
      setSelectedProjectId(projId)
      setWindowHash(`#analysis?id=${projId}`)
    } else {
      setWindowHash("#analysis")
    }
    setCurrentPage("analysis")
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

  if (activePage === "analysis") {
    return (
      <AnalysisPage
        projectId={selectedProjectId}
        onNavigateDashboard={() => navigateTo("dashboard")}
        onNavigateLanding={() => navigateTo("landing")}
        onSignOut={() => void handleSignOut()}
      />
    )
  }

  if (activePage === "dashboard") {
    return (
      <DashboardPage
        onNavigateLanding={() => navigateTo("landing")}
        onNavigateAnalysis={(projId) => navigateToAnalysis(projId)}
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
