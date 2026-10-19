import { useEffect, useState } from "react"
import { LandingPage } from "@/pages/LandingPage"
import { LoginPage } from "@/pages/LoginPage"

export function App() {
  const [currentPage, setCurrentPage] = useState<"landing" | "login">(() => {
    if (typeof window !== "undefined") {
      const hash = window.location.hash.toLowerCase()
      if (hash === "#signin" || hash === "#/login" || hash === "#login") {
        return "login"
      }
    }
    return "landing"
  })

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.toLowerCase()
      if (hash === "#signin" || hash === "#/login" || hash === "#login") {
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

  if (currentPage === "login") {
    return <LoginPage onNavigateLanding={navigateToLanding} />
  }

  return <LandingPage onNavigateLogin={navigateToLogin} />
}
