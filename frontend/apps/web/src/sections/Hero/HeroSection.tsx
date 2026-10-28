import { Button } from "@workspace/ui/components/button"
import { landingContent } from "@/config/content/landing"
import { HeroGraph } from "./HeroGraph"

interface HeroSectionProps {
  onAnalyze?: () => void
}

export function HeroSection({ onAnalyze }: HeroSectionProps) {
  const { hero } = landingContent

  const handleAnalyzeClick = (e: React.MouseEvent) => {
    if (onAnalyze) {
      e.preventDefault()
      onAnalyze()
    }
  }

  return (
    <section
      className="mx-auto max-w-[1440px] border-b border-hairline px-4 pt-12 pb-20 sm:px-6 md:px-12 md:pt-16 md:pb-28"
      id="hero"
    >
      <div className="grid grid-cols-1 items-start gap-12 lg:grid-cols-12 lg:gap-16">
        {/* Left Editorial Copy (7 cols) */}
        <div className="flex flex-col justify-between lg:col-span-7">
          <div>
            {/* Category / Engine Tag */}
            <div className="mb-4 inline-flex items-center gap-2 border border-hairline bg-surface-container-low px-2.5 py-1">
              <span className="inline-block size-1.5 rotate-45 bg-gold" />
              <span className="font-mono text-[11px] font-medium tracking-wider text-ink uppercase">
                {hero.engineTag}
              </span>
            </div>

            {/* Headline with Two-Weight Tension */}
            <h1 className="mb-6 text-left leading-[1.05]">
              <span
                className="block font-sans text-4xl tracking-tight text-ink sm:text-5xl md:text-[56px]"
                style={{ fontWeight: "var(--headline-weight-contrast, 300)" }}
              >
                {hero.titleLight}
              </span>
              <span className="block font-sans text-4xl font-bold tracking-tight text-ink sm:text-5xl md:text-[56px]">
                {hero.titleBold}
              </span>
            </h1>

            {/* Serif Narrative Copy */}
            <p className="mb-10 max-w-xl text-left font-serif text-[18px] leading-relaxed text-neutral-600 md:text-[19px]">
              {hero.description}
            </p>
          </div>

          {/* CTA Row & Guarantees */}
          <div className="pt-2">
            <div className="mb-10 flex flex-wrap items-center gap-6">
              <a href="#dashboard" onClick={handleAnalyzeClick}>
                <Button size="lg" className="group">
                  <span>{hero.primaryCta}</span>
                  <span className="transition-transform duration-150 group-hover:translate-x-1">
                    →
                  </span>
                </Button>
              </a>
              <a
                href="#architecture"
                className="font-serif text-[16px] text-ink underline decoration-ink underline-offset-4 transition-colors duration-150 hover:text-accent hover:decoration-accent"
              >
                {hero.secondaryCta}
              </a>
            </div>

            {/* Privacy Checklist */}
            <div className="grid max-w-lg grid-cols-3 gap-4 border-t border-hairline pt-6">
              {hero.metrics.map((metric) => (
                <div key={metric.label}>
                  <div className="font-mono text-[11px] font-medium tracking-wider text-neutral-500 uppercase">
                    {metric.label}
                  </div>
                  <div className="mt-0.5 font-sans text-[17px] font-semibold text-ink">
                    {metric.value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Graph Chamber (5 cols) */}
        <div className="flex flex-col lg:col-span-5">
          <HeroGraph />
        </div>
      </div>
    </section>
  )
}
