import { landingContent } from "@/config/content/landing"
import { SectionHeader } from "@/components/SectionHeader"

interface ExecutionModesProps {
  onNavigateLogin?: () => void
}

export function ExecutionModes({ onNavigateLogin }: ExecutionModesProps) {
  const { executionModes } = landingContent
  const { localMode, cloudMode, aiDisclosure } = executionModes

  return (
    <section
      className="mx-auto max-w-[1440px] border-b border-hairline px-4 py-16 sm:px-6 md:px-12 md:py-20"
      id="modes"
    >
      <SectionHeader
        indexLabel={executionModes.index}
        lightTitle={executionModes.titleLight}
        boldTitle={executionModes.titleBold}
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Mode 1: Local Engine */}
        <div className="relative flex flex-col justify-between rounded-[0px] border border-hairline bg-surface-white p-6 text-left md:p-8">
          <div className="absolute top-4 right-4">
            <span className="inline-flex items-center gap-1.5 border border-hairline bg-surface-container px-2 py-0.5 font-mono text-[10px] tracking-wider text-ink uppercase">
              <span className="inline-block size-1.5 bg-gold" />
              {localMode.badge}
            </span>
          </div>

          <div>
            <div className="mb-3 font-mono text-xs tracking-wider text-neutral-500 uppercase">
              {localMode.runtime}
            </div>
            <h3 className="mb-4 font-sans text-2xl font-bold text-ink">
              {localMode.title}
            </h3>
            <p className="mb-6 font-serif text-[15px] leading-relaxed text-neutral-600 md:text-[16px]">
              {localMode.desc}
            </p>

            <ul className="space-y-3 border-t border-hairline pt-6 font-mono text-xs text-ink">
              {localMode.points.map((point) => (
                <li key={point} className="flex items-center gap-2">
                  <span className="flex size-3 items-center justify-center bg-ink text-[9px] text-paper">
                    ✓
                  </span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-8 flex items-center justify-between border-t border-hairline pt-6">
            <span className="font-mono text-xs text-neutral-500">
              {localMode.meta}
            </span>
            <a
              href="#docs"
              className="font-sans text-[11px] font-bold tracking-wider text-ink uppercase transition-colors hover:text-accent"
            >
              {localMode.cta}
            </a>
          </div>
        </div>

        {/* Mode 2: Cloud Workspace */}
        <div className="relative flex flex-col justify-between rounded-[0px] border border-hairline bg-surface-white p-6 text-left md:p-8">
          <div className="absolute top-4 right-4">
            <span className="inline-flex items-center gap-1.5 border border-hairline bg-surface-container px-2 py-0.5 font-mono text-[10px] tracking-wider text-ink uppercase">
              {cloudMode.badge}
            </span>
          </div>

          <div>
            <div className="mb-3 font-mono text-xs tracking-wider text-neutral-500 uppercase">
              {cloudMode.runtime}
            </div>
            <h3 className="mb-4 font-sans text-2xl font-bold text-ink">
              {cloudMode.title}
            </h3>
            <p className="mb-6 font-serif text-[15px] leading-relaxed text-neutral-600 md:text-[16px]">
              {cloudMode.desc}
            </p>

            <ul className="space-y-3 border-t border-hairline pt-6 font-mono text-xs text-ink">
              {cloudMode.points.map((point) => (
                <li key={point} className="flex items-center gap-2">
                  <span className="flex size-3 items-center justify-center bg-ink text-[9px] text-paper">
                    ✓
                  </span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-8 flex items-center justify-between border-t border-hairline pt-6">
            <span className="font-mono text-xs text-neutral-500">
              {cloudMode.meta}
            </span>
            <a
              href="#signin"
              onClick={(e) => {
                if (onNavigateLogin) {
                  e.preventDefault()
                  onNavigateLogin()
                }
              }}
              className="cursor-pointer font-sans text-[11px] font-bold tracking-wider text-ink uppercase transition-colors hover:text-accent"
            >
              {cloudMode.cta}
            </a>
          </div>
        </div>
      </div>

      {/* AI Disclosure Strip */}
      <div className="mt-8 flex flex-col justify-between gap-3 border border-hairline bg-surface-container p-4 text-left font-mono text-xs sm:flex-row sm:items-center">
        <div className="flex items-center gap-2.5">
          <span className="inline-block size-2 shrink-0 bg-gold" />
          <span className="font-semibold text-ink">{aiDisclosure.title}</span>
        </div>
        <div className="text-neutral-500">{aiDisclosure.desc}</div>
      </div>
    </section>
  )
}
