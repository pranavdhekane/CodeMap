import { useState } from "react"
import { Menu, X } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Logo } from "@/components/Logo"
import { landingContent } from "@/config/content/landing"
import { isLocalMode } from "@/config/mode"

interface NavbarProps {
  isAuthenticated?: boolean
  userEmail?: string
  onNavigateLogin?: () => void
  onNavigateLanding?: () => void
  onNavigateDashboard?: () => void
  onSignOut?: () => void
}

export function Navbar({
  isAuthenticated = false,
  userEmail = "c.babbage@synthetic-ast.org",
  onNavigateLogin,
  onNavigateLanding,
  onNavigateDashboard,
  onSignOut,
}: NavbarProps) {
  const { nav } = landingContent
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const isLocal = isLocalMode()

  const handleBrandClick = (e: React.MouseEvent) => {
    if (isAuthenticated) {
      if (onNavigateDashboard) {
        e.preventDefault()
        onNavigateDashboard()
      }
    } else {
      if (onNavigateLanding) {
        e.preventDefault()
        onNavigateLanding()
      }
    }
  }

  const handleAnalyzeClick = (e: React.MouseEvent) => {
    if (onNavigateDashboard) {
      e.preventDefault()
      onNavigateDashboard()
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-paper/95 backdrop-blur-none transition-colors duration-150">
      <div className="mx-auto flex h-16 w-full max-w-[1440px] items-center justify-between px-4 sm:px-6 md:px-12">
        {/* Brand Logo & Left Nav */}
        <div className="flex items-center gap-8 md:gap-12">
          <a
            href={isAuthenticated ? "#dashboard" : "#hero"}
            onClick={handleBrandClick}
            className="group focus:outline-none"
          >
            <Logo />
          </a>

          {/* Desktop Navigation Links */}
          {isAuthenticated ? (
            <nav className="hidden items-center gap-6 md:flex">
              <a
                href="#dashboard"
                onClick={(e) => {
                  e.preventDefault()
                  onNavigateDashboard?.()
                }}
                className="border-b border-ink pb-0.5 font-sans text-[11px] font-bold tracking-wider text-ink uppercase"
              >
                Dashboard
              </a>
              <a
                href="#docs"
                className="font-sans text-[11px] font-semibold tracking-wider text-neutral-500 uppercase transition-colors duration-150 hover:text-ink"
              >
                Docs
              </a>
            </nav>
          ) : (
            <nav className="hidden items-center gap-8 md:flex">
              {nav.links.map((link, idx) => (
                <a
                  key={link.label}
                  href={link.href}
                  className={`font-sans text-[11px] font-bold tracking-wider uppercase transition-colors duration-150 ${
                    idx === 0
                      ? "border-b border-ink pb-0.5 text-ink"
                      : "text-neutral-500 hover:text-accent"
                  }`}
                >
                  {link.label}
                </a>
              ))}
            </nav>
          )}
        </div>

        {/* Trailing Action Cluster */}
        {isAuthenticated ? (
          <div className="flex items-center gap-6">
            {isLocal ? (
              <div className="flex items-center gap-2 font-mono text-[11px] text-neutral-600">
                <span className="inline-block size-1.5 rotate-45 bg-gold" />
                <span className="font-semibold tracking-wider uppercase">
                  AIR-GAPPED · LOCAL
                </span>
              </div>
            ) : (
              <div className="hidden items-center gap-2 font-mono text-[11px] text-neutral-500 sm:flex">
                <span className="size-1.5 bg-gold" />
                <span>{userEmail}</span>
              </div>
            )}

            {isLocal ? (
              <button
                type="button"
                onClick={onNavigateLanding}
                className="group inline-flex cursor-pointer items-center gap-1.5 font-sans text-[11px] font-bold tracking-wider text-ink uppercase underline decoration-hairline underline-offset-4 transition-colors hover:text-accent hover:decoration-accent"
              >
                <span>Landing page</span>
                <span className="transition-transform duration-150 group-hover:translate-x-0.5">
                  →
                </span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  if (onSignOut) {
                    onSignOut()
                  } else if (onNavigateLanding) {
                    onNavigateLanding()
                  }
                }}
                className="group inline-flex cursor-pointer items-center gap-1.5 font-sans text-[11px] font-bold tracking-wider text-ink uppercase underline decoration-hairline underline-offset-4 transition-colors hover:text-accent hover:decoration-accent"
              >
                <span>Sign out</span>
                <span className="transition-transform duration-150 group-hover:translate-x-1">
                  →
                </span>
              </button>
            )}
          </div>
        ) : (
          <div className="hidden items-center gap-6 sm:flex">
            {isLocal ? (
              <div className="flex items-center gap-1.5 font-mono text-[11px] tracking-wider text-neutral-500 uppercase">
                <span className="inline-block size-1.5 rotate-45 bg-gold" />
                <span>LOCAL OFFLINE</span>
              </div>
            ) : (
              <a
                href={nav.signIn.href}
                onClick={(e) => {
                  if (onNavigateLogin) {
                    e.preventDefault()
                    onNavigateLogin()
                  }
                }}
                className="cursor-pointer font-sans text-[11px] font-bold tracking-wider text-neutral-500 uppercase transition-colors duration-150 hover:text-ink"
              >
                {nav.signIn.label}
              </a>
            )}

            <a href="#dashboard" onClick={handleAnalyzeClick}>
              <Button size="sm" className="group">
                <span>{nav.analyzeCta.label}</span>
                <span className="transition-transform duration-150 group-hover:translate-x-0.5">
                  →
                </span>
              </Button>
            </a>
          </div>
        )}

        {/* Mobile Menu Button (Unauthenticated) */}
        {!isAuthenticated && (
          <div className="flex items-center gap-2 sm:hidden">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="border border-hairline p-1.5 text-ink"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? (
                <X className="size-5" strokeWidth={1.5} />
              ) : (
                <Menu className="size-5" strokeWidth={1.5} />
              )}
            </button>
          </div>
        )}
      </div>

      {/* Mobile Drawer (Unauthenticated) */}
      {!isAuthenticated && mobileMenuOpen && (
        <div className="flex flex-col gap-4 border-b border-hairline bg-paper px-6 py-4 font-mono text-xs sm:hidden">
          {nav.links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={() => setMobileMenuOpen(false)}
              className="py-1 font-sans text-[12px] font-bold tracking-wider text-ink uppercase"
            >
              {link.label}
            </a>
          ))}
          <div className="flex flex-col gap-3 border-t border-hairline pt-3">
            {!isLocal && (
              <a
                href={nav.signIn.href}
                onClick={(e) => {
                  setMobileMenuOpen(false)
                  if (onNavigateLogin) {
                    e.preventDefault()
                    onNavigateLogin()
                  }
                }}
                className="cursor-pointer font-sans text-[11px] font-bold tracking-wider text-neutral-500 uppercase"
              >
                {nav.signIn.label}
              </a>
            )}
            <a
              href="#dashboard"
              onClick={(e) => {
                setMobileMenuOpen(false)
                handleAnalyzeClick(e)
              }}
            >
              <Button size="sm" className="w-full">
                {nav.analyzeCta.label} →
              </Button>
            </a>
          </div>
        </div>
      )}
    </header>
  )
}
