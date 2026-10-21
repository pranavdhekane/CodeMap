import { Logo } from "@/components/Logo"
import { landingContent } from "@/config/content/landing"

export function Footer() {
  const { footer } = landingContent

  return (
    <footer className="border-t border-hairline bg-surface-container-low transition-colors duration-150">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col items-center justify-between gap-6 px-4 py-12 sm:px-6 md:flex-row md:px-12">
        {/* Left Metadata & Copyright */}
        <div className="flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left">
          <Logo />
          <span className="hidden text-neutral-300 sm:inline">|</span>
          <span className="font-mono text-xs font-medium text-neutral-600">
            {footer.credit}
          </span>
          <span className="hidden text-neutral-300 sm:inline">|</span>
          <p className="font-serif text-[14px] text-neutral-500">
            {footer.copyright}
          </p>
        </div>

        {/* Links List */}
        <div className="flex flex-wrap items-center justify-center gap-6 font-mono text-[11px]">
          {footer.links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-neutral-500 underline underline-offset-4 transition-colors hover:text-accent"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Version Stamp */}
        <div className="border border-hairline bg-surface-white px-2 py-1 font-mono text-[11px] text-neutral-500">
          {footer.version}
        </div>
      </div>
    </footer>
  )
}
