import { useState } from "react"
import { Menu, X } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Logo } from "@/components/Logo"
import { landingContent } from "@/config/content/landing"

interface NavbarProps {
  onNavigateLogin?: () => void
}

export function Navbar({ onNavigateLogin }: NavbarProps) {
  const { nav } = landingContent
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-paper/95 backdrop-blur-none transition-colors duration-150">
      <div className="mx-auto flex h-16 w-full max-w-[1440px] items-center justify-between px-4 sm:px-6 md:px-12">
        {/* Brand Logo */}
        <a href="#hero" className="group focus:outline-none">
          <Logo />
        </a>

        {/* Desktop Navigation Links */}
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

        {/* Trailing Action Cluster */}
        <div className="hidden items-center gap-6 sm:flex">
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
          <a href={nav.analyzeCta.href}>
            <Button size="sm" className="group">
              <span>{nav.analyzeCta.label}</span>
              <span className="transition-transform duration-150 group-hover:translate-x-0.5">
                →
              </span>
            </Button>
          </a>
        </div>

        {/* Mobile Menu Button */}
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
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
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
            <a
              href={nav.analyzeCta.href}
              onClick={() => setMobileMenuOpen(false)}
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
