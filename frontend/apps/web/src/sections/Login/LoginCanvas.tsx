import { loginContent } from "@/config/content/login"

export function LoginCanvas() {
  const { canvasRight } = loginContent

  return (
    <section className="relative flex min-h-[620px] w-full flex-col justify-between overflow-hidden border-t border-dark-hairline bg-dark-surface p-6 text-ivory select-none sm:p-10 lg:min-h-auto lg:w-[55%] lg:border-t-0 lg:p-12 xl:p-14">
      {/* Subtle Hairline Grid Dot Pattern Background (No glow, no blur) */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage: "radial-gradient(#F7F5F0 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
        aria-hidden="true"
      />

      {/* Top Status Header */}
      <div className="relative z-10 flex items-center justify-between border-b border-dark-hairline pb-6 text-left">
        <div className="flex items-center gap-2.5">
          <div className="inline-block size-2 shrink-0 rotate-45 bg-gold" />
          <span className="font-mono text-[11px] font-semibold tracking-[0.14em] text-neutral-300 uppercase">
            {canvasRight.statusBadge}
          </span>
        </div>
        <div className="hidden items-center gap-2 border border-dark-hairline px-2.5 py-1 font-mono text-[10px] text-dark-muted sm:flex">
          <span>SOCKETS: 0</span>
          <span>·</span>
          <span className="text-neutral-300">SANDBOX: JAIL_ROOT</span>
        </div>
      </div>

      {/* Centered Interactive Dependency Graph Visual */}
      <div className="relative z-10 my-auto flex flex-col items-center justify-center py-8">
        {/* Live Graph HUD Header */}
        <div className="mb-3 flex w-full max-w-[580px] items-center justify-between px-1 text-left font-mono text-[11px] text-dark-muted">
          <div className="flex items-center gap-2">
            <span className="inline-block size-1.5 shrink-0 bg-accent" />
            <span>{canvasRight.topologyHeader}</span>
          </div>
          <span className="text-dark-muted">{canvasRight.cycleAlert}</span>
        </div>

        {/* SVG Container for Dependency Network */}
        <div className="relative h-[340px] w-full max-w-[580px] overflow-hidden rounded-[0px] border border-dark-hairline bg-dark-elevated p-4">
          {/* Coordinates readout */}
          <div className="absolute top-2.5 left-3 font-mono text-[9px] text-neutral-600">
            CANVAS: AST_MEM_MAP_0x89FA
          </div>
          <div className="absolute top-2.5 right-3 font-mono text-[9px] text-neutral-600">
            {canvasRight.resolutionGauge}
          </div>

          {/* SVG Graph Network */}
          <svg
            className="h-full w-full"
            fill="none"
            viewBox="0 0 540 280"
            aria-label="Encrypted AST Dependency Network"
          >
            <defs>
              <marker
                id="login-arrow-accent"
                markerHeight="6"
                markerWidth="6"
                orient="auto-start-reverse"
                refX="7"
                refY="5"
                viewBox="0 0 10 10"
              >
                <path
                  d="M 0 1 L 8 5 L 0 9 z"
                  fill="var(--editorial-accent, #4B2BB5)"
                />
              </marker>
              <marker
                id="login-arrow-neutral"
                markerHeight="5"
                markerWidth="5"
                orient="auto-start-reverse"
                refX="7"
                refY="5"
                viewBox="0 0 10 10"
              >
                <path d="M 0 1 L 8 5 L 0 9 z" fill="#47464A" />
              </marker>
            </defs>

            {/* Standard edges */}
            <g stroke="#2A2A30" strokeWidth="1.2">
              <line
                markerEnd="url(#login-arrow-neutral)"
                x1="120"
                y1="75"
                x2="240"
                y2="65"
              />
              <line
                markerEnd="url(#login-arrow-neutral)"
                x1="240"
                y1="65"
                x2="380"
                y2="90"
              />
              <line
                markerEnd="url(#login-arrow-neutral)"
                x1="120"
                y1="75"
                x2="150"
                y2="190"
              />
              <line
                markerEnd="url(#login-arrow-neutral)"
                x1="150"
                y1="190"
                x2="320"
                y2="200"
              />
            </g>

            {/* Highlighted Cycle Edge in Royal Violet */}
            <g>
              <path
                className="cycle-highlight-pulse"
                d="M 380 90 C 420 150, 370 210, 320 200"
                fill="none"
                markerEnd="url(#login-arrow-accent)"
                stroke="var(--editorial-accent, #4B2BB5)"
                strokeWidth="2"
              />
              <path
                d="M 320 200 C 280 130, 200 110, 240 65"
                fill="none"
                stroke="var(--editorial-accent, #4B2BB5)"
                strokeDasharray="4 3"
                strokeWidth="1.5"
              />
            </g>

            {/* Node 1: kernel/ast.py */}
            <g transform="translate(50, 55)">
              <rect
                fill="#161618"
                height="32"
                stroke="#2A2A30"
                strokeWidth="1"
                width="120"
              />
              <circle cx="12" cy="16" fill="#B8923A" r="3" />
              <text
                fill="#F7F5F0"
                fontFamily="'JetBrains Mono', monospace"
                fontSize="10"
                x="24"
                y="20"
              >
                kernel/ast.py
              </text>
            </g>

            {/* Node 2: graph/toposort.py */}
            <g transform="translate(180, 45)">
              <rect
                fill="#161618"
                height="32"
                stroke="#2A2A30"
                strokeWidth="1"
                width="130"
              />
              <circle cx="12" cy="16" fill="#858386" r="3" />
              <text
                fill="#F7F5F0"
                fontFamily="'JetBrains Mono', monospace"
                fontSize="10"
                x="24"
                y="20"
              >
                toposort.py
              </text>
            </g>

            {/* Node 3: blast_radius.py */}
            <g transform="translate(80, 175)">
              <rect
                fill="#161618"
                height="32"
                stroke="#2A2A30"
                strokeWidth="1"
                width="130"
              />
              <circle cx="12" cy="16" fill="#858386" r="3" />
              <text
                fill="#F7F5F0"
                fontFamily="'JetBrains Mono', monospace"
                fontSize="10"
                x="24"
                y="20"
              >
                blast_radius.py
              </text>
            </g>

            {/* Node 4: detect_cycle.py (Flagged with violet accent border) */}
            <g transform="translate(320, 75)">
              <rect
                fill="#18132B"
                height="32"
                stroke="var(--editorial-accent, #4B2BB5)"
                strokeWidth="1.5"
                width="140"
              />
              <rect
                fill="var(--editorial-accent, #4B2BB5)"
                height="32"
                width="3"
                x="0"
                y="0"
              />
              <circle
                cx="14"
                cy="16"
                fill="var(--editorial-accent, #4B2BB5)"
                r="3"
              />
              <text
                fill="#F7F5F0"
                fontFamily="'JetBrains Mono', monospace"
                fontSize="10"
                fontWeight="600"
                x="25"
                y="20"
              >
                detect_cycle.py
              </text>
            </g>

            {/* Node 5: local_keyring.py */}
            <g transform="translate(260, 185)">
              <rect
                fill="#161618"
                height="32"
                stroke="#2A2A30"
                strokeWidth="1"
                width="135"
              />
              <circle cx="12" cy="16" fill="#B8923A" r="3" />
              <text
                fill="#F7F5F0"
                fontFamily="'JetBrains Mono', monospace"
                fontSize="10"
                x="24"
                y="20"
              >
                local_keyring.py
              </text>
            </g>
          </svg>

          {/* Cycle Breaker Callout Chip Overlay */}
          <div className="absolute bottom-3 left-3 flex items-center gap-2 border border-accent bg-[#18132B] px-3 py-1.5">
            <span className="inline-block size-1.5 shrink-0 bg-accent" />
            <div className="flex flex-col text-left">
              <span className="font-mono text-[9px] font-semibold tracking-wider text-purple-300 uppercase">
                {canvasRight.cycleBreaker.label}
              </span>
              <span className="font-mono text-[10px] text-ivory">
                {canvasRight.cycleBreaker.cut}
              </span>
            </div>
          </div>
        </div>

        {/* Terminal Trace Output */}
        <div className="mt-3 flex w-full max-w-[580px] items-center justify-between px-1 font-mono text-xs text-dark-muted">
          <span className="text-neutral-500">{canvasRight.terminalTrace}</span>
          <span className="font-mono text-[10px] text-dark-muted">
            {canvasRight.terminalStatus}
          </span>
        </div>
      </div>

      {/* Bottom Anchor Typography & Air-Gap Manifesto */}
      <div className="relative z-10 border-t border-dark-hairline pt-6 text-left">
        <div className="flex items-center gap-2 font-mono text-xs text-dark-muted">
          <span className="text-accent select-none">$</span>
          <span className="font-semibold text-neutral-300">
            {canvasRight.terminalCommand}
          </span>
        </div>
        <p className="mt-2 font-serif text-2xl tracking-tight text-ivory italic lg:text-3xl">
          {canvasRight.quote}
        </p>
        <p className="mt-1.5 font-mono text-xs tracking-wide text-dark-muted">
          {canvasRight.quoteSubtext}
        </p>
      </div>
    </section>
  )
}
