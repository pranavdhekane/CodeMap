import { Code2, Network, FileText } from "lucide-react"
import { landingContent } from "@/config/content/landing"
import { SectionHeader } from "@/components/SectionHeader"

const stageIcons = [
  <Code2 key="parse" className="size-4 text-ink" strokeWidth={1.5} />,
  <Network key="map" className="size-4 text-ink" strokeWidth={1.5} />,
  <FileText key="understand" className="size-4 text-ink" strokeWidth={1.5} />,
]

export function ArchitecturePipeline() {
  const { architecture } = landingContent

  return (
    <section
      className="mx-auto max-w-[1440px] border-b border-hairline px-4 py-16 sm:px-6 md:px-12 md:py-20"
      id="architecture"
    >
      <SectionHeader
        indexLabel={architecture.index}
        lightTitle={architecture.titleLight}
        boldTitle={architecture.titleBold}
      />

      {/* 3-Column Planar Grid */}
      <div className="grid grid-cols-1 border-t border-l border-hairline md:grid-cols-3">
        {architecture.stages.map((stage, idx) => (
          <div
            key={stage.stage}
            className="flex flex-col justify-between border-r border-b border-hairline bg-paper p-6 transition-colors duration-150 hover:bg-[#EFECE4] md:p-8"
          >
            <div>
              {/* Header: Stage tag + 1.5px icon */}
              <div className="mb-8 flex items-center justify-between">
                <span className="font-mono text-[11px] tracking-wider text-neutral-500 uppercase">
                  {stage.stage}
                </span>
                <div className="flex size-8 items-center justify-center border border-hairline bg-surface-white">
                  {stageIcons[idx]}
                </div>
              </div>

              {/* Title & Serif Body */}
              <h3 className="mb-3 font-sans text-[12px] font-bold tracking-wider text-ink uppercase">
                {stage.title}
              </h3>
              <p className="text-left font-serif text-[15px] leading-relaxed text-neutral-600 md:text-[16px]">
                {stage.desc}
              </p>
            </div>

            {/* Bottom Meta */}
            <div className="mt-8 border-t border-hairline pt-4 font-mono text-[11px] text-neutral-500">
              {stage.meta}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
