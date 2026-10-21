import { useState } from "react"
import { landingContent, type HeroGraphNode } from "@/config/content/landing"

export function HeroGraph() {
  const { graph } = landingContent.hero
  const [selectedNodeId, setSelectedNodeId] = useState<string>("user")
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)

  const activeNodeId = hoveredNodeId || selectedNodeId
  const activeNode =
    graph.nodes.find((n) => n.id === activeNodeId) || graph.nodes[1]

  // Connected nodes map for highlighting neighbors
  const connectedNodeIds = new Set<string>()
  connectedNodeIds.add(activeNodeId)
  graph.edges.forEach((edge) => {
    if (edge.from === activeNodeId) connectedNodeIds.add(edge.to)
    if (edge.to === activeNodeId) connectedNodeIds.add(edge.from)
  })

  return (
    <div className="flex h-full flex-col justify-between rounded-[0px] border border-hairline bg-surface-white p-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between border-b border-hairline pb-3">
        <div className="flex items-center gap-2">
          <span className="inline-block size-1.5 bg-gold" />
          <span className="font-mono text-[11px] tracking-wider text-neutral-500 uppercase">
            {graph.headerTag}
          </span>
        </div>
        <div className="border border-hairline bg-surface-container px-1.5 py-0.5 font-mono text-[10px] text-neutral-500">
          {graph.modulesMeta}
        </div>
      </div>

      {/* SVG Canvas Container */}
      <div className="relative flex min-h-[360px] flex-grow items-center justify-center overflow-hidden border border-hairline bg-paper select-none">
        <svg
          className="h-full max-h-[380px] w-full"
          viewBox="0 0 460 380"
          aria-label="AST Dependency Directed Graph"
        >
          {/* Directed Edges */}
          <g stroke="#C8C5CA" strokeDasharray="3 3" strokeWidth="1.2">
            <line
              x1="230"
              y1="60"
              x2="130"
              y2="150"
              strokeOpacity={
                activeNodeId === "router" || activeNodeId === "user" ? 1 : 0.4
              }
            />
            <line
              x1="230"
              y1="60"
              x2="330"
              y2="150"
              strokeOpacity={
                activeNodeId === "router" || activeNodeId === "auth" ? 1 : 0.4
              }
            />
            <line
              x1="130"
              y1="150"
              x2="130"
              y2="280"
              strokeOpacity={
                activeNodeId === "user" || activeNodeId === "db" ? 1 : 0.4
              }
            />
            <line
              x1="330"
              y1="150"
              x2="330"
              y2="280"
              strokeOpacity={
                activeNodeId === "auth" || activeNodeId === "crypto" ? 1 : 0.4
              }
            />
            <line
              x1="230"
              y1="330"
              x2="130"
              y2="280"
              strokeOpacity={
                activeNodeId === "worker" || activeNodeId === "db" ? 1 : 0.4
              }
            />
            <line
              x1="230"
              y1="330"
              x2="330"
              y2="280"
              strokeOpacity={
                activeNodeId === "worker" || activeNodeId === "crypto" ? 1 : 0.4
              }
            />
          </g>

          {/* Circular Cycle Edges (user <-> auth) */}
          <path
            className="cycle-highlight-pulse"
            d="M 148 142 C 220 110, 240 110, 312 142"
            fill="none"
            stroke="var(--editorial-accent, #4B2BB5)"
            strokeWidth="2"
          />
          <path
            className="cycle-highlight-pulse"
            d="M 312 158 C 240 190, 220 190, 148 158"
            fill="none"
            stroke="var(--editorial-accent, #4B2BB5)"
            strokeWidth="2"
          />

          {/* Cycle Badge Indicator */}
          <rect
            x="185"
            y="142"
            width="90"
            height="18"
            rx="1"
            fill="var(--editorial-accent, #4B2BB5)"
          />
          <text
            x="230"
            y="154"
            textAnchor="middle"
            fill="#FFFFFF"
            fontFamily="'JetBrains Mono', monospace"
            fontSize="9"
            fontWeight="600"
          >
            {graph.cycleLabel}
          </text>

          {/* Graph Nodes */}
          {graph.nodes.map((node: HeroGraphNode) => {
            const isSelected = node.id === activeNodeId
            const isNeighbor = connectedNodeIds.has(node.id)
            const opacity = isSelected || isNeighbor ? 1 : 0.35

            return (
              <g
                key={node.id}
                className="cursor-pointer transition-opacity duration-150"
                transform={`translate(${node.x}, ${node.y})`}
                opacity={opacity}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                onClick={() => setSelectedNodeId(node.id)}
              >
                {/* Selection ring if active */}
                {isSelected && (
                  <circle
                    r={node.radius + 6}
                    fill="none"
                    stroke="var(--editorial-accent, #4B2BB5)"
                    strokeWidth="1"
                    strokeDasharray="2 2"
                  />
                )}
                {/* Node outer circle */}
                <circle
                  r={node.radius}
                  fill="#FFFFFF"
                  stroke={
                    node.isHighlighted
                      ? "var(--editorial-accent, #4B2BB5)"
                      : "#0E0E10"
                  }
                  strokeWidth={isSelected ? 2.5 : 1.5}
                  className="transition-all duration-150"
                />
                {/* Node center dot */}
                <circle
                  r={4}
                  fill={
                    node.isHighlighted
                      ? "var(--editorial-accent, #4B2BB5)"
                      : "#0E0E10"
                  }
                />
                {/* Node label */}
                <text
                  y={node.radius + 14}
                  textAnchor="middle"
                  fill="#0E0E10"
                  fontFamily="'JetBrains Mono', monospace"
                  fontSize="10"
                  fontWeight={isSelected ? "700" : "500"}
                >
                  {node.name}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Floating Inspector Card */}
        <div className="absolute right-3 bottom-3 left-3 flex items-center justify-between border border-hairline bg-surface-white p-3 font-mono text-xs shadow-none select-text">
          <div>
            <span className="block text-[10px] tracking-wider text-neutral-500 uppercase">
              INSPECTED SYMBOL:
            </span>
            <span className="text-[12px] font-semibold text-ink">
              {activeNode.name}
            </span>
          </div>
          <div className="flex gap-4 text-right">
            <div>
              <span className="block text-[10px] text-neutral-500 uppercase">
                FAN-IN / OUT
              </span>
              <span className="font-semibold text-ink">{activeNode.fan}</span>
            </div>
            <div>
              <span className="block text-[10px] text-neutral-500 uppercase">
                LOC
              </span>
              <span className="font-semibold text-ink">{activeNode.loc}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Micro Readout */}
      <div className="mt-4 flex flex-col justify-between gap-1 border-t border-hairline pt-3 font-mono text-[11px] text-neutral-500 sm:flex-row sm:items-center">
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-1.5 bg-accent" />
          {graph.note}
        </span>
        <span className="font-semibold text-ink">{graph.fix}</span>
      </div>
    </div>
  )
}
