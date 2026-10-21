interface SectionHeaderProps {
  indexLabel: string
  lightTitle: string
  boldTitle: string
  className?: string
  isInverted?: boolean
}

export function SectionHeader({
  indexLabel,
  lightTitle,
  boldTitle,
  className = "",
  isInverted = false,
}: SectionHeaderProps) {
  return (
    <div className={`mb-10 text-left ${className}`}>
      <div
        className={`mb-3 font-mono text-[11px] font-medium tracking-wider uppercase ${
          isInverted ? "text-dark-muted" : "text-neutral-500"
        }`}
      >
        {indexLabel}
      </div>
      <h2 className="text-left font-sans text-3xl leading-[1.1] tracking-tight md:text-5xl">
        <span
          className={`font-light ${isInverted ? "text-ivory" : "text-ink"}`}
          style={{ fontWeight: "var(--headline-weight-contrast, 300)" }}
        >
          {lightTitle}
        </span>
        <span className={`font-bold ${isInverted ? "text-ivory" : "text-ink"}`}>
          {boldTitle}
        </span>
      </h2>
    </div>
  )
}
