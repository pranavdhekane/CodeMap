interface LogoProps {
  className?: string
  showText?: boolean
}

export function Logo({ className = "", showText = true }: LogoProps) {
  return (
    <div
      className={`inline-flex items-center gap-2.5 select-none ${className}`}
    >
      <svg
        className="size-5 shrink-0 text-ink dark:text-ivory"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle cx="6" cy="6" r="3.5" />
        <circle cx="18" cy="18" r="3.5" />
        <path d="M8.5 8.5L15.5 15.5" strokeDasharray="2 2" />
      </svg>
      {showText && (
        <span className="font-sans text-sm font-bold tracking-tight text-ink uppercase dark:text-ivory">
          CodeMap
        </span>
      )}
    </div>
  )
}
