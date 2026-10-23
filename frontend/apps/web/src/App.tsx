import { useEffect, useState } from "react"
import { LandingPage } from "@/pages/LandingPage"
import { LoginPage } from "@/pages/LoginPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { getCurrentUser, signOut } from "@/api/auth"

type Page = "landing" | "login" | "dashboard"

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isCheckingAuth, setIsCheckingAuth] = useState(true)
  const [currentPage, setCurrentPage] = useState<Page>(() => {
    if (typeof window !== "undefined") {
      const hash = window.location.hash.toLowerCase()
      if (
        hash === "#dashboard" ||
        hash === "#/dashboard" ||
        hash === "#projects"
      ) {
        return "dashboard"
      }
      if (hash === "#signin" || hash === "#/login" || hash === "#login") {
        return "login"
      }
    }
    return "landing"
  })

  useEffect(() => {
    void getCurrentUser().then((user) => {
      setIsAuthenticated(Boolean(user))
      setIsCheckingAuth(false)
    })

    const handleHashChange = () => {
      const hash = window.location.hash.toLowerCase()
      if (
        hash === "#dashboard" ||
        hash === "#/dashboard" ||
        hash === "#projects"
      ) {
        setCurrentPage("dashboard")
      } else if (
        hash === "#signin" ||
        hash === "#/login" ||
        hash === "#login"
      ) {
        setCurrentPage("login")
      } else if (
        hash === "#landing" ||
        hash === "#/" ||
        hash === "" ||
        hash === "#hero"
      ) {
        setCurrentPage("landing")
      }
    }

    window.addEventListener("hashchange", handleHashChange)
    return () => window.removeEventListener("hashchange", handleHashChange)
  }, [])

  const navigateToLogin = () => {
    setCurrentPage("login")
    window.location.hash = "#signin"
    window.scrollTo({ top: 0, behavior: "instant" })
  }

  const navigateToLanding = () => {
    setCurrentPage("landing")
    window.location.hash = "#hero"
    window.scrollTo({ top: 0, behavior: "instant" })
  }

  const navigateToDashboard = () => {
    setIsAuthenticated(true)
    setCurrentPage("dashboard")
    window.location.hash = "#dashboard"
    window.scrollTo({ top: 0, behavior: "instant" })
  }

  const handleSignOut = async () => {
    await signOut()
    setIsAuthenticated(false)
    navigateToLogin()
  }

  if (isCheckingAuth) {
    return <div className="min-h-screen bg-paper" />
  }

  if (currentPage === "dashboard") {
    if (!isAuthenticated) {
      return (
        <LoginPage
          onNavigateLanding={navigateToLanding}
          onNavigateDashboard={navigateToDashboard}
        />
      )
    }
    return (
      <DashboardPage
        onNavigateLanding={navigateToLanding}
        onSignOut={() => void handleSignOut()}
      />
    )
  }

  if (currentPage === "login") {
    return (
      <LoginPage
        onNavigateLanding={navigateToLanding}
        onNavigateDashboard={navigateToDashboard}
      />
    )
  }

  return <LandingPage onNavigateLogin={navigateToLogin} />
}
