import { useEffect, useState } from "react"
import { landingContent } from "@/config/content/landing"
import { useInView } from "@/hooks/useInView"
import { useReducedMotion } from "@/hooks/useReducedMotion"

export function FeatureShowcase() {
  const { featureShowcase } = landingContent
  const [containerRef, isInView] = useInView<HTMLElement>({ threshold: 0.2 })
  const prefersReduced = useReducedMotion()
  const [blastCount, setBlastCount] = useState(() =>
    prefersReduced ? featureShowcase.nodeDetails.blastRadiusCount : 0
  )

  useEffect(() => {
    if (!isInView || prefersReduced) return

    let current = 0
    const target = featureShowcase.nodeDetails.blastRadiusCount
    const timer = setInterval(() => {
      current++
      setBlastCount(current)
      if (current >= target) {
        clearInterval(timer)
      }
    }, 50)

    return () => clearInterval(timer)
  }, [isInView, prefersReduced, featureShowcase.nodeDetails.blastRadiusCount])

  const effectiveBlastCount = prefersReduced
    ? featureShowcase.nodeDetails.blastRadiusCount
    : blastCount

  return (
    <section
      ref={containerRef}
      className="border-y border-dark-hairline bg-dark-surface px-4 py-16 text-ivory sm:px-6 md:px-12 md:py-24"
      id="features"
    >
      <div className="mx-auto max-w-[1440px]">
        {/* Chamber Header */}
        <div className="flex flex-col justify-between gap-4 border-b border-dark-hairline pb-8 text-left md:flex-row md:items-end md:pb-10">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 font-mono text-[11px] tracking-wider text-dark-muted uppercase">
              <span className="inline-block size-1.5 bg-gold" />
              <span>{featureShowcase.badge}</span>
            </div>
            <h2 className="text-left font-sans text-3xl font-bold tracking-tight text-ivory md:text-5xl">
              {featureShowcase.title}
            </h2>
          </div>
          <div className="self-start border border-dark-hairline bg-dark-surface px-3 py-1.5 font-mono text-xs text-dark-muted md:self-auto">
            TARGET: {featureShowcase.targetFile}
          </div>
        </div>

        {/* Product Simulation Window */}
        <div className="mt-8 border border-dark-hairline bg-dark-surface">
          {/* Window Chrome */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-dark-hairline px-4 py-3 font-mono text-xs text-dark-muted">
            <div className="flex items-center gap-2">
              <span className="inline-block size-2 border border-dark-subtle" />
              <span className="inline-block size-2 border border-dark-subtle" />
              <span className="inline-block size-2 border border-dark-subtle" />
              <span className="ml-3 text-ivory">
                {featureShowcase.workspaceTitle}
              </span>
            </div>
            <div className="flex items-center gap-4 text-[11px]">
              <span>AST: PYTHON_3.11+</span>
              <span className="font-medium text-gold">
                ● {featureShowcase.parserStatus}
              </span>
            </div>
          </div>

          {/* Window Grid: Graph Canvas (8 cols) + Inspector Drawer (4 cols) */}
          <div className="grid min-h-[480px] grid-cols-1 lg:grid-cols-12">
            {/* Graph Canvas */}
            <div className="relative flex flex-col justify-between border-b border-dark-hairline p-6 lg:col-span-8 lg:border-r lg:border-b-0">
              <div className="flex items-center justify-between font-mono text-xs text-dark-muted">
                <span>{featureShowcase.clusterLabel}</span>
                <span className="font-semibold tracking-wide text-accent">
                  {featureShowcase.cycleAlert}
                </span>
              </div>

              {/* Inverted Dark SVG Graph */}
              <div className="relative my-6 flex items-center justify-center">
                <svg
                  className="h-[320px] w-full max-w-[620px]"
                  viewBox="0 0 600 320"
                  aria-label="Inspection Chamber Dependency Graph"
                >
                  {/* Hairline Connections */}
                  <g stroke="#2A2A30" strokeWidth="1.2">
                    <line x1="80" y1="160" x2="220" y2="80" />
                    <line x1="80" y1="160" x2="220" y2="240" />
                    <line x1="220" y1="80" x2="380" y2="80" />
                    <line x1="220" y1="240" x2="380" y2="240" />
                    <line x1="380" y1="80" x2="520" y2="160" />
                    <line x1="380" y1="240" x2="520" y2="160" />
                  </g>

                  {/* Circular Cycle Edge between checkout.py and invoice_gen.py */}
                  <path
                    className="cycle-highlight-pulse"
                    d="M 380 80 C 460 140, 300 180, 220 240"
                    fill="none"
                    stroke="var(--editorial-accent, #4B2BB5)"
                    strokeDasharray="4 2"
                    strokeWidth="2"
                  />

                  {/* Node 1: gateway.py */}
                  <g transform="translate(80, 160)">
                    <circle
                      r="16"
                      fill="#1B1B1D"
                      stroke="#47464A"
                      strokeWidth="1.5"
                    />
                    <text
                      y="28"
                      textAnchor="middle"
                      fill="#858386"
                      fontFamily="'JetBrains Mono', monospace"
                      fontSize="10"
                    >
                      gateway.py
                    </text>
                  </g>

                  {/* Node 2: checkout.py (Selected Node) */}
                  <g transform="translate(220, 80)">
                    <circle
                      r="20"
                      fill="#0E0E10"
                      stroke="#FFFFFF"
                      strokeWidth="2"
                    />
                    <circle r="4" fill="var(--editorial-accent, #4B2BB5)" />
                    <text
                      y="32"
                      textAnchor="middle"
                      fill="#FFFFFF"
                      fontFamily="'JetBrains Mono', monospace"
                      fontSize="11"
                      fontWeight="700"
                    >
                      checkout.py
                    </text>
                    <circle
                      r="26"
                      fill="none"
                      stroke="var(--editorial-accent, #4B2BB5)"
                      strokeDasharray="2 2"
                      strokeWidth="1"
                    />
                  </g>

                  {/* Node 3: intent.py */}
                  <g transform="translate(380, 80)">
                    <circle
                      r="16"
                      fill="#1B1B1D"
                      stroke="#47464A"
                      strokeWidth="1.5"
                    />
                    <text
                      y="28"
                      textAnchor="middle"
                      fill="#858386"
                      fontFamily="'JetBrains Mono', monospace"
                      fontSize="10"
                    >
                      intent.py
                    </text>
                  </g>

                  {/* Node 4: invoice_gen.py */}
                  <g transform="translate(220, 240)">
                    <circle
                      r="16"
                      fill="#1B1B1D"
                      stroke="var(--editorial-accent, #4B2BB5)"
                      strokeWidth="1.5"
                    />
                    <text
                      y="28"
                      textAnchor="middle"
                      fill="#FFFFFF"
                      fontFamily="'JetBrains Mono', monospace"
                      fontSize="10"
                    >
                      invoice_gen.py
                    </text>
                  </g>

                  {/* Node 5: ledger.py */}
                  <g transform="translate(380, 240)">
                    <circle
                      r="16"
                      fill="#1B1B1D"
                      stroke="#47464A"
                      strokeWidth="1.5"
                    />
                    <text
                      y="28"
                      textAnchor="middle"
                      fill="#858386"
                      fontFamily="'JetBrains Mono', monospace"
                      fontSize="10"
                    >
                      ledger.py
                    </text>
                  </g>

                  {/* Node 6: webhook.py */}
                  <g transform="translate(520, 160)">
                    <circle
                      r="16"
                      fill="#1B1B1D"
                      stroke="#47464A"
                      strokeWidth="1.5"
                    />
                    <text
                      y="28"
                      textAnchor="middle"
                      fill="#858386"
                      fontFamily="'JetBrains Mono', monospace"
                      fontSize="10"
                    >
                      webhook.py
                    </text>
                  </g>
                </svg>
              </div>

              {/* Cycle Cut Suggestion Callout */}
              <div className="flex flex-col justify-between gap-2 border border-accent/40 bg-accent/10 p-3 font-mono text-xs sm:flex-row sm:items-center">
                <span className="text-ivory">
                  <strong className="font-bold text-gold">
                    SUGGESTED CUT:
                  </strong>{" "}
                  Remove direct call from `invoice_gen.py` to `checkout.py`
                </span>
                <span className="cursor-pointer text-dark-muted underline transition-colors hover:text-white">
                  {featureShowcase.cutLink}
                </span>
              </div>
            </div>

            {/* Inspector Drawer (4 cols) */}
            <div className="flex flex-col justify-between bg-dark-elevated p-6 lg:col-span-4">
              <div>
                <div className="flex items-center justify-between border-b border-dark-hairline pb-4">
                  <span className="font-sans text-[11px] font-bold tracking-wider text-dark-muted uppercase">
                    NODE INSPECTION
                  </span>
                  <span className="bg-accent px-2 py-0.5 font-mono text-[10px] text-white">
                    SELECTED
                  </span>
                </div>

                {/* Module Path */}
                <div className="border-b border-dark-hairline py-4 text-left">
                  <div className="mb-1 font-mono text-[10px] tracking-wider text-dark-muted uppercase">
                    QUALIFIED PATH
                  </div>
                  <div className="font-mono text-xs font-semibold break-all text-ivory md:text-sm">
                    {featureShowcase.nodeDetails.qualifiedPath}
                  </div>
                </div>

                {/* Metric Grid */}
                <div className="grid grid-cols-2 gap-4 border-b border-dark-hairline py-4 text-left font-mono text-xs">
                  <div>
                    <span className="block text-[10px] text-dark-muted uppercase">
                      COUPLING STATUS
                    </span>
                    <span className="text-warning font-bold">
                      {featureShowcase.nodeDetails.couplingStatus}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-dark-muted uppercase">
                      BLAST RADIUS
                    </span>
                    <span className="font-bold text-ivory">
                      {effectiveBlastCount} modules impacted
                    </span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-dark-muted uppercase">
                      DIRECT DEPENDENTS
                    </span>
                    <span className="text-ivory">
                      {featureShowcase.nodeDetails.directDependents}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-dark-muted uppercase">
                      UPSTREAM IMPORTS
                    </span>
                    <span className="text-ivory">
                      {featureShowcase.nodeDetails.upstreamImports}
                    </span>
                  </div>
                </div>

                {/* Cyclomatic Complexity */}
                <div className="py-4 text-left font-mono text-xs">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-[10px] text-dark-muted uppercase">
                      CYCLOMATIC COMPLEXITY
                    </span>
                    <span className="font-bold text-red-400">
                      {featureShowcase.nodeDetails.cyclomaticComplexity}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-dark-hairline">
                    <div
                      className="h-1.5 bg-red-500"
                      style={{
                        width: featureShowcase.nodeDetails.cyclomaticPercentage,
                      }}
                    />
                  </div>
                  <span className="mt-2 block text-[10px] text-dark-muted">
                    {featureShowcase.nodeDetails.recommendation}
                  </span>
                </div>
              </div>

              {/* Action Button */}
              <button
                type="button"
                className="mt-6 w-full cursor-pointer rounded-[2px] bg-paper py-2.5 font-sans text-[11px] font-bold tracking-wider text-ink uppercase transition-colors hover:bg-white active:bg-accent active:text-white"
              >
                {featureShowcase.nodeDetails.actionButton}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
