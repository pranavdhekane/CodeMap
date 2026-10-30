import { Button } from "@workspace/ui/components/button"
import { landingContent } from "@/config/content/landing"

interface FinalCtaProps {
  onAnalyze?: () => void
}

export function FinalCta({ onAnalyze }: FinalCtaProps) {
  const { finalCta } = landingContent

  const handleAnalyzeClick = (e: React.MouseEvent) => {
    if (onAnalyze) {
      e.preventDefault()
      onAnalyze()
    }
  }

  return (
    <section
      className="mx-auto max-w-[1440px] border-b border-hairline px-4 py-20 text-left sm:px-6 md:px-12 md:py-24"
      id="analyze"
    >
      <div className="max-w-3xl">
        <div className="mb-4 font-mono text-[11px] font-medium tracking-wider text-neutral-500 uppercase">
          {finalCta.badge}
        </div>

        <h2 className="mb-6 text-left text-4xl leading-[1.08] tracking-tight sm:text-5xl md:text-6xl">
          <span
            className="font-sans font-light text-ink"
            style={{ fontWeight: "var(--headline-weight-contrast, 300)" }}
          >
            {finalCta.titleLight}
          </span>
          <span className="font-sans font-bold text-ink">
            {finalCta.titleBold}
          </span>
        </h2>

        <p className="mb-10 max-w-xl text-left font-serif text-[18px] leading-relaxed text-neutral-600 md:text-[19px]">
          {finalCta.description}
        </p>

        <div className="mb-8 flex flex-col items-stretch gap-4 sm:flex-row sm:items-center">
          <a href="#dashboard" onClick={handleAnalyzeClick}>
            <Button size="lg" className="group w-full sm:w-auto">
              <span>{finalCta.primaryCta}</span>
              <span className="transition-transform duration-150 group-hover:translate-x-1">
                →
              </span>
            </Button>
          </a>
          <a href="#docs">
            <Button variant="outline" size="lg" className="w-full sm:w-auto">
              {finalCta.secondaryCta}
            </Button>
          </a>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs text-neutral-500">
          <span className="text-neutral-400 select-none">$</span>
          <span className="border border-hairline bg-surface-container px-2 py-1 text-ink">
            {finalCta.command}
          </span>
        </div>
      </div>
    </section>
  )
}
