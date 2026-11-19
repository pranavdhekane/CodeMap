import { useState, useEffect, useMemo } from "react"
import {
  ArrowLeft,
  Download,
  AlertCircle,
  Search,
  FileCode,
  Info,
  Trash2,
} from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Navbar } from "@/sections/Navbar/Navbar"
import { Footer } from "@/sections/Footer/Footer"
import { TweaksPanel } from "@/components/TweaksPanel"
import { dashboardContent } from "@/config/content/dashboard"
import {
  fetchProjects,
  fetchProject,
  fetchAnalysisRun,
  deleteProject,
  type ProjectItem,
  type AnalysisRunDetails,
  type RunSymbol,
  formatRelativeTime,
} from "@/api/projects"

interface AnalysisPageProps {
  projectId?: string | null
  onNavigateDashboard: () => void
  onNavigateLanding?: () => void
  onSignOut?: () => void
}

type TabType = "graph" | "findings" | "modules" | "symbols"

export function AnalysisPage({
  projectId,
  onNavigateDashboard,
  onNavigateLanding,
  onSignOut,
}: AnalysisPageProps) {
  const [project, setProject] = useState<ProjectItem | null>(null)
  const [run, setRun] = useState<AnalysisRunDetails | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const [isDeleting, setIsDeleting] = useState(false)
  const [activeTab, setActiveTab] = useState<TabType>("graph")
  const [graphMode, setGraphMode] = useState<"import" | "call">("import")
  const [searchQuery, setSearchQuery] = useState("")
  const [severityFilter, setSeverityFilter] = useState<string>("all")
  const [symbolKindFilter, setSymbolKindFilter] = useState<string>("all")
  const [selectedNodeKey, setSelectedNodeKey] = useState<string | null>(null)

  // Load project & run details
  useEffect(() => {
    let isMounted = true

    const loadData = async () => {
      try {
        setIsLoading(true)
        setErrorMessage(null)

        let targetId = projectId ? parseInt(projectId, 10) : NaN
        let proj: ProjectItem | null = null

        if (isNaN(targetId)) {
          // If no specific project ID was passed, grab the latest project
          const allProjects = await fetchProjects()
          if (allProjects.length > 0) {
            proj = allProjects[0]
            targetId = proj.project_id
          } else {
            throw new Error("No analyzed projects found in workspace.")
          }
        } else {
          proj = await fetchProject(targetId)
        }

        if (!isMounted) return
        setProject(proj)

        const runId = proj.latest_run?.run_id
        if (!runId) {
          throw new Error("This project has no completed analysis runs yet.")
        }

        const runData = await fetchAnalysisRun(runId)
        if (!isMounted) return
        setRun(runData)
      } catch (err: unknown) {
        if (!isMounted) return
        const msg = err instanceof Error ? err.message : "Failed to load analysis details"
        setErrorMessage(msg)
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    void loadData()
    return () => {
      isMounted = false
    }
  }, [projectId])

  // Computed metrics
  const totalLoc = useMemo(() => {
    if (!run) return 0
    let lines = 0
    for (const sym of run.symbols) {
      if (sym.kind === "module" && sym.metrics?.lines) {
        lines += sym.metrics.lines
      }
    }
    return lines
  }, [run])

  const classCount = useMemo(() => {
    return run?.symbols.filter((s) => s.kind === "class").length ?? 0
  }, [run])

  const functionCount = useMemo(() => {
    return run?.symbols.filter((s) => s.kind === "function" || s.kind === "method").length ?? 0
  }, [run])

  const cycleCount = useMemo(() => {
    return run?.findings.filter((f) => f.type.includes("cycle")).length ?? 0
  }, [run])

  // Filtered Findings
  const filteredFindings = useMemo(() => {
    if (!run) return []
    return run.findings.filter((f) => {
      if (severityFilter !== "all" && f.severity !== severityFilter) return false
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchDesc = f.description.toLowerCase().includes(q)
        const matchType = f.type.toLowerCase().includes(q)
        const matchSym = f.symbols.some((s) => s.toLowerCase().includes(q))
        return matchDesc || matchType || matchSym
      }
      return true
    })
  }, [run, severityFilter, searchQuery])

  // Filtered Symbols
  const filteredSymbols = useMemo(() => {
    if (!run) return []
    return run.symbols.filter((s) => {
      if (symbolKindFilter !== "all" && s.kind !== symbolKindFilter) return false
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        return s.name.toLowerCase().includes(q) || s.stable_key.toLowerCase().includes(q)
      }
      return true
    })
  }, [run, symbolKindFilter, searchQuery])

  // Filtered Files
  const filteredFiles = useMemo(() => {
    if (!run) return []
    if (!searchQuery.trim()) return run.files
    const q = searchQuery.toLowerCase().trim()
    return run.files.filter((f) => f.path.toLowerCase().includes(q))
  }, [run, searchQuery])

  // Delete Project handler
  const handleDeleteProject = async () => {
    if (!project) return
    const confirmed = window.confirm(
      `Are you sure you want to remove "${project.name}" from your CodeMap history? This will delete all its analysis data.`
    )
    if (!confirmed) return

    try {
      setIsDeleting(true)
      await deleteProject(project.project_id)
      onNavigateDashboard()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to remove project"
      alert(msg)
      setIsDeleting(false)
    }
  }

  // Export JSON handler
  const handleExportJson = () => {
    if (!run || !project) return
    const blob = new Blob([JSON.stringify({ project, run }, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `codemap-analysis-${project.name.toLowerCase().replace(/\s+/g, "-")}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Graph Layout generation
  const graphNodesAndEdges = useMemo(() => {
    if (!run) return { nodes: [], edges: [] }

    if (graphMode === "import") {
      const moduleSymbols = run.symbols.filter((s) => s.kind === "module")
      const relevantKeys = new Set(moduleSymbols.map((m) => m.stable_key))

      const rawEdges = run.edges.filter(
        (e) => e.kind === "imports" && e.target && relevantKeys.has(e.target) && relevantKeys.has(e.source)
      )

      // Layout in a circle
      const radius = 240
      const cx = 380
      const cy = 250
      const n = moduleSymbols.length
      const nodes = moduleSymbols.map((mod, idx) => {
        const angle = n > 0 ? (2 * Math.PI * idx) / n : 0
        const x = cx + radius * Math.cos(angle)
        const y = cy + radius * Math.sin(angle)
        return {
          id: mod.stable_key,
          label: mod.name,
          fullKey: mod.stable_key,
          x,
          y,
          kind: "module",
          data: mod,
        }
      })

      const nodeMap = new Map(nodes.map((n) => [n.id, n]))
      const edges = rawEdges
        .map((e) => {
          const s = nodeMap.get(e.source)
          const t = e.target ? nodeMap.get(e.target) : null
          if (!s || !t) return null
          return { source: s, target: t, kind: e.kind }
        })
        .filter(Boolean)

      return { nodes, edges }
    } else {
      // Call graph
      const funcSymbols = run.symbols.filter((s) => s.kind === "function" || s.kind === "method").slice(0, 30)
      const relevantKeys = new Set(funcSymbols.map((f) => f.stable_key))

      const rawEdges = run.edges.filter(
        (e) => e.kind === "calls" && e.target && relevantKeys.has(e.target) && relevantKeys.has(e.source)
      )

      const radius = 240
      const cx = 380
      const cy = 250
      const n = funcSymbols.length
      const nodes = funcSymbols.map((fn, idx) => {
        const angle = n > 0 ? (2 * Math.PI * idx) / n : 0
        const x = cx + radius * Math.cos(angle)
        const y = cy + radius * Math.sin(angle)
        return {
          id: fn.stable_key,
          label: fn.name,
          fullKey: fn.stable_key,
          x,
          y,
          kind: fn.kind,
          data: fn,
        }
      })

      const nodeMap = new Map(nodes.map((n) => [n.id, n]))
      const edges = rawEdges
        .map((e) => {
          const s = nodeMap.get(e.source)
          const t = e.target ? nodeMap.get(e.target) : null
          if (!s || !t) return null
          return { source: s, target: t, kind: e.kind }
        })
        .filter(Boolean)

      return { nodes, edges }
    }
  }, [run, graphMode])

  // Selected node details
  const selectedNodeSymbol = useMemo<RunSymbol | null>(() => {
    if (!run || !selectedNodeKey) return null
    return run.symbols.find((s) => s.stable_key === selectedNodeKey) || null
  }, [run, selectedNodeKey])

  return (
    <div className="flex min-h-screen flex-col overflow-x-hidden bg-paper font-sans text-ink antialiased selection:bg-accent selection:text-paper">
      <Navbar
        isAuthenticated={true}
        userEmail={dashboardContent.nav.userEmail}
        onNavigateLanding={onNavigateLanding}
        onNavigateDashboard={onNavigateDashboard}
        onSignOut={onSignOut || onNavigateLanding}
      />

      <main className="mx-auto flex w-full max-w-[1440px] flex-grow flex-col px-6 py-6 md:px-12 md:py-10">
        {/* Navigation & Breadcrumbs */}
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={onNavigateDashboard}
            className="group flex cursor-pointer items-center gap-2 font-mono text-[11px] font-bold tracking-wider text-ink uppercase hover:text-accent"
          >
            <ArrowLeft className="size-3.5 transition-transform group-hover:-translate-x-1" />
            <span>Back to Workspace</span>
          </button>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDeleteProject}
              disabled={!project || isDeleting}
              className="cursor-pointer gap-2 border border-red-300 bg-surface-white px-3 py-1.5 font-mono text-xs font-bold text-red-700 hover:border-red-400 hover:bg-red-50"
            >
              <Trash2 className="size-3.5 text-red-600" />
              <span>{isDeleting ? "Removing..." : "Remove Project"}</span>
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleExportJson}
              disabled={!run}
              className="cursor-pointer gap-2 border border-hairline bg-surface-white px-3 py-1.5 font-mono text-xs font-bold text-ink hover:bg-row-hover"
            >
              <Download className="size-3.5" />
              <span>Export JSON</span>
            </Button>
          </div>
        </div>

        {/* Error Notification */}
        {errorMessage && (
          <div className="mb-8 flex items-start gap-3 border border-red-500/30 bg-red-50 p-4 text-red-900">
            <AlertCircle className="size-5 shrink-0 text-red-600" />
            <div>
              <h4 className="font-sans text-sm font-bold">Failed to load analysis</h4>
              <p className="mt-1 font-mono text-xs">{errorMessage}</p>
            </div>
          </div>
        )}

        {/* Loading Spinner */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <div className="mb-4 size-8 animate-spin rounded-full border-2 border-ink border-t-transparent" />
            <span className="font-mono text-xs tracking-wider text-neutral-500 uppercase">
              Extracting AST architecture & dependency matrix...
            </span>
          </div>
        ) : run && project ? (
          <>
            {/* Header Strip */}
            <header className="border-b border-hairline pb-8">
              <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 font-mono text-[10px] font-bold tracking-widest text-neutral-500 uppercase">
                    <span className="size-1.5 bg-gold" />
                    <span>01 / ANALYSIS DOSSIER</span>
                    <span>·</span>
                    <span>AST BASIC_ALGO_1</span>
                    <span>·</span>
                    <span>{formatRelativeTime(run.scanned_at)}</span>
                  </div>
                  <h1 className="font-sans text-3xl font-bold tracking-tight text-ink md:text-4xl">
                    {project.name}
                  </h1>
                  <p className="font-serif text-sm text-neutral-600 italic">
                    {project.description ||
                      "Deterministic static AST scan — all code executed in an ephemeral sandbox and discarded."}
                  </p>
                </div>

                <div className="flex items-center gap-2 font-mono text-[11px] text-neutral-500">
                  <span className="text-gold">◆</span>
                  <span>Commit: {run.commit_hash || "HEAD"}</span>
                </div>
              </div>

              {/* 5-KPI Metric Bar */}
              <div className="mt-8 grid grid-cols-2 gap-px border border-hairline bg-hairline sm:grid-cols-3 lg:grid-cols-5">
                {/* Metric 1: Scale */}
                <div className="bg-paper p-4">
                  <span className="font-mono text-[10px] font-bold tracking-wider text-neutral-500 uppercase">
                    Files & LOC
                  </span>
                  <div className="mt-2 font-sans text-2xl font-bold text-ink">
                    {run.files.length}{" "}
                    <span className="font-serif text-sm font-normal text-neutral-500">
                      / {totalLoc.toLocaleString()} lines
                    </span>
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-neutral-400">
                    {run.files.length} python modules
                  </div>
                </div>

                {/* Metric 2: Symbols */}
                <div className="bg-paper p-4">
                  <span className="font-mono text-[10px] font-bold tracking-wider text-neutral-500 uppercase">
                    Symbols
                  </span>
                  <div className="mt-2 font-sans text-2xl font-bold text-ink">
                    {run.symbols.length}{" "}
                    <span className="font-serif text-sm font-normal text-neutral-500">
                      total
                    </span>
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-neutral-400">
                    {functionCount} funcs · {classCount} classes
                  </div>
                </div>

                {/* Metric 3: Edges */}
                <div className="bg-paper p-4">
                  <span className="font-mono text-[10px] font-bold tracking-wider text-neutral-500 uppercase">
                    Dependency Edges
                  </span>
                  <div className="mt-2 font-sans text-2xl font-bold text-ink">
                    {run.edges.length}
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-neutral-400">
                    calls, imports & inheritance
                  </div>
                </div>

                {/* Metric 4: Cycles */}
                <div className="bg-paper p-4">
                  <span className="font-mono text-[10px] font-bold tracking-wider text-neutral-500 uppercase">
                    Cycles Flagged
                  </span>
                  <div
                    className={`mt-2 font-sans text-2xl font-bold ${
                      cycleCount > 0 ? "text-red-700" : "text-ink"
                    }`}
                  >
                    {cycleCount}
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-neutral-400">
                    {cycleCount > 0 ? "Circular import/call paths" : "No cycles detected"}
                  </div>
                </div>

                {/* Metric 5: Findings */}
                <div className="col-span-2 bg-paper p-4 sm:col-span-1">
                  <span className="font-mono text-[10px] font-bold tracking-wider text-neutral-500 uppercase">
                    Quality Findings
                  </span>
                  <div className="mt-2 font-sans text-2xl font-bold text-accent">
                    {run.findings.length}
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-neutral-400">
                    dead code, unused, missing
                  </div>
                </div>
              </div>
            </header>

            {/* Navigation Tabs & Search Controls */}
            <div className="mt-6 flex flex-col justify-between gap-4 border-b border-hairline pb-2 sm:flex-row sm:items-center">
              <div className="flex items-center gap-6 font-mono text-xs font-bold uppercase">
                <button
                  onClick={() => {
                    setActiveTab("graph")
                    setSelectedNodeKey(null)
                  }}
                  className={`cursor-pointer pb-2.5 transition-colors ${
                    activeTab === "graph"
                      ? "border-b-2 border-accent text-accent"
                      : "text-neutral-500 hover:text-ink"
                  }`}
                >
                  Overview & Graph
                </button>
                <button
                  onClick={() => setActiveTab("findings")}
                  className={`cursor-pointer pb-2.5 transition-colors ${
                    activeTab === "findings"
                      ? "border-b-2 border-accent text-accent"
                      : "text-neutral-500 hover:text-ink"
                  }`}
                >
                  Findings ({run.findings.length})
                </button>
                <button
                  onClick={() => setActiveTab("modules")}
                  className={`cursor-pointer pb-2.5 transition-colors ${
                    activeTab === "modules"
                      ? "border-b-2 border-accent text-accent"
                      : "text-neutral-500 hover:text-ink"
                  }`}
                >
                  Modules ({run.files.length})
                </button>
                <button
                  onClick={() => setActiveTab("symbols")}
                  className={`cursor-pointer pb-2.5 transition-colors ${
                    activeTab === "symbols"
                      ? "border-b-2 border-accent text-accent"
                      : "text-neutral-500 hover:text-ink"
                  }`}
                >
                  Symbols ({run.symbols.length})
                </button>
              </div>

              {/* Search Bar */}
              <div className="relative flex items-center min-w-[240px]">
                <Search className="absolute left-2 size-3.5 text-neutral-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter symbols, files, issues..."
                  className="w-full border-b border-hairline bg-transparent py-1 pl-7 pr-2 font-mono text-xs text-ink placeholder:text-neutral-400 focus:border-b-2 focus:border-accent focus:outline-none"
                />
              </div>
            </div>

            {/* Tab 1: Overview & Graph Chamber */}
            {activeTab === "graph" && (
              <div className="mt-6 flex flex-col border border-hairline bg-[#0E0E10] text-[#F7F5F0]">
                {/* Chamber Toolbar */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#2A2A30] px-4 py-2.5 font-mono text-[11px]">
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-neutral-400 uppercase">MODE:</span>
                    <button
                      onClick={() => {
                        setGraphMode("import")
                        setSelectedNodeKey(null)
                      }}
                      className={`cursor-pointer px-2.5 py-1 uppercase ${
                        graphMode === "import"
                          ? "bg-[#2A2A30] font-bold text-white"
                          : "text-neutral-400 hover:text-white"
                      }`}
                    >
                      Import Graph
                    </button>
                    <button
                      onClick={() => {
                        setGraphMode("call")
                        setSelectedNodeKey(null)
                      }}
                      className={`cursor-pointer px-2.5 py-1 uppercase ${
                        graphMode === "call"
                          ? "bg-[#2A2A30] font-bold text-white"
                          : "text-neutral-400 hover:text-white"
                      }`}
                    >
                      Call Graph
                    </button>
                  </div>

                  <div className="flex items-center gap-3 text-neutral-400">
                    <span>
                      {graphNodesAndEdges.nodes.length} nodes · {graphNodesAndEdges.edges.length} edges
                    </span>
                    <span className="text-gold">◆</span>
                    <span className="text-[10px] text-gold uppercase">Deterministic AST</span>
                  </div>
                </div>

                {/* Graph View & Inspector Split */}
                <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[520px]">
                  {/* Interactive SVG Canvas */}
                  <div className="relative flex items-center justify-center overflow-hidden bg-[#0A0A0C] p-4 lg:col-span-8">
                    {/* Grid Pattern */}
                    <div
                      className="absolute inset-0 pointer-events-none opacity-20"
                      style={{
                        backgroundImage:
                          "linear-gradient(to right, #2A2A30 1px, transparent 1px), linear-gradient(to bottom, #2A2A30 1px, transparent 1px)",
                        backgroundSize: "40px 40px",
                      }}
                    />

                    {graphNodesAndEdges.nodes.length === 0 ? (
                      <div className="z-10 font-mono text-xs text-neutral-500">
                        No graph nodes available for this view.
                      </div>
                    ) : (
                      <svg viewBox="0 0 760 500" className="h-full w-full max-h-[500px]">
                        <defs>
                          <marker
                            id="arrow"
                            viewBox="0 0 10 10"
                            refX="18"
                            refY="5"
                            markerWidth="6"
                            markerHeight="6"
                            orient="auto-start-reverse"
                          >
                            <path d="M 0 0 L 10 5 L 0 10 z" fill="#785ee4" opacity="0.6" />
                          </marker>
                        </defs>

                        {/* Edges */}
                        {graphNodesAndEdges.edges.map((e, idx) => {
                          if (!e) return null
                          const isConnected =
                            selectedNodeKey &&
                            (e.source.id === selectedNodeKey || e.target.id === selectedNodeKey)
                          return (
                            <line
                              key={idx}
                              x1={e.source.x}
                              y1={e.source.y}
                              x2={e.target.x}
                              y2={e.target.y}
                              stroke={isConnected ? "#785ee4" : "#2A2A30"}
                              strokeWidth={isConnected ? 2 : 1.2}
                              strokeDasharray={e.kind === "inherits" ? "4 3" : undefined}
                              markerEnd="url(#arrow)"
                              opacity={isConnected ? 0.9 : 0.4}
                            />
                          )
                        })}

                        {/* Nodes */}
                        {graphNodesAndEdges.nodes.map((node) => {
                          const isSelected = selectedNodeKey === node.id
                          return (
                            <g
                              key={node.id}
                              transform={`translate(${node.x}, ${node.y})`}
                              onClick={() => setSelectedNodeKey(node.id)}
                              className="cursor-pointer transition-transform duration-150 hover:scale-110"
                            >
                              <circle
                                r={isSelected ? 10 : 7}
                                fill={
                                  node.kind === "module"
                                    ? isSelected
                                      ? "#785ee4"
                                      : "#B8923A"
                                    : isSelected
                                      ? "#785ee4"
                                      : "#5f43c9"
                                }
                                stroke={isSelected ? "#ffffff" : "#0E0E10"}
                                strokeWidth={2}
                              />
                              <text
                                x={12}
                                y={4}
                                fill={isSelected ? "#ffffff" : "#A0A0A5"}
                                fontSize="11"
                                fontFamily="monospace"
                                fontWeight={isSelected ? "bold" : "normal"}
                              >
                                {node.label}
                              </text>
                            </g>
                          )
                        })}
                      </svg>
                    )}
                  </div>

                  {/* Inspector Sidebar */}
                  <div className="flex flex-col border-t border-[#2A2A30] bg-[#121215] p-5 font-mono text-xs lg:col-span-4 lg:border-t-0 lg:border-l">
                    <div className="mb-4 flex items-center justify-between border-b border-[#2A2A30] pb-2">
                      <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
                        NODE INSPECTOR
                      </span>
                      {selectedNodeKey && (
                        <button
                          onClick={() => setSelectedNodeKey(null)}
                          className="cursor-pointer text-[10px] text-neutral-400 hover:text-white"
                        >
                          CLEAR
                        </button>
                      )}
                    </div>

                    {selectedNodeSymbol ? (
                      <div className="space-y-4">
                        <div>
                          <span className="text-[10px] text-neutral-500 uppercase">IDENTIFIER</span>
                          <h4 className="font-bold text-white break-all text-sm">
                            {selectedNodeSymbol.name}
                          </h4>
                          <p className="mt-0.5 text-[11px] text-neutral-400 break-all">
                            {selectedNodeSymbol.stable_key}
                          </p>
                        </div>

                        <div>
                          <span className="text-[10px] text-neutral-500 uppercase">KIND & FILE</span>
                          <div className="mt-1 flex items-center gap-2">
                            <span className="border border-[#2A2A30] bg-[#1a1a20] px-1.5 py-0.5 text-[10px] font-bold text-gold uppercase">
                              {selectedNodeSymbol.kind}
                            </span>
                            <span className="text-[11px] text-neutral-300">
                              {selectedNodeSymbol.file || "—"}
                            </span>
                          </div>
                        </div>

                        {selectedNodeSymbol.metrics && Object.keys(selectedNodeSymbol.metrics).length > 0 && (
                          <div>
                            <span className="text-[10px] text-neutral-500 uppercase">METRICS</span>
                            <div className="mt-1 grid grid-cols-2 gap-2 text-[11px]">
                              {Object.entries(selectedNodeSymbol.metrics).map(([k, v]) => (
                                <div key={k} className="border border-[#2A2A30] bg-[#1a1a20] p-1.5">
                                  <span className="text-neutral-400 uppercase text-[9px]">{k}:</span>{" "}
                                  <span className="font-bold text-white">{v}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {selectedNodeSymbol.signature && selectedNodeSymbol.signature.length > 0 && (
                          <div>
                            <span className="text-[10px] text-neutral-500 uppercase">SIGNATURE</span>
                            <div className="mt-1 space-y-1">
                              {selectedNodeSymbol.signature.map((item, idx) => (
                                <div
                                  key={idx}
                                  className="flex items-center justify-between border-b border-[#222228] py-0.5 text-[11px]"
                                >
                                  <span className="text-neutral-400">
                                    {item.role === "return" ? "returns" : item.name}:
                                  </span>
                                  <span className="text-accent">{item.type || "Any"}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        <div>
                          <span className="text-[10px] text-neutral-500 uppercase">CONNECTED EDGES</span>
                          <div className="mt-1 max-h-40 overflow-y-auto space-y-1 text-[11px] text-neutral-300">
                            {run.edges
                              .filter(
                                (e) =>
                                  e.source === selectedNodeSymbol.stable_key ||
                                  e.target === selectedNodeSymbol.stable_key
                              )
                              .map((e, idx) => (
                                <div
                                  key={idx}
                                  className="border border-[#2A2A30] bg-[#16161b] p-1.5 flex items-center justify-between"
                                >
                                  <span className="truncate">
                                    {e.source === selectedNodeSymbol.stable_key ? "→ calls" : "← called by"}{" "}
                                    {e.target || e.target_reference || "unresolved"}
                                  </span>
                                  <span className="text-[9px] text-neutral-500 uppercase">
                                    {e.kind}
                                  </span>
                                </div>
                              ))}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-16 text-center text-neutral-500">
                        <Info className="mb-2 size-5" />
                        <p className="text-xs">Click on any node in the graph to inspect its AST metrics and references.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Findings View */}
            {activeTab === "findings" && (
              <div className="mt-6 space-y-4">
                {/* Findings Filter Bar */}
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-neutral-500 uppercase text-[10px] font-bold">Severity:</span>
                  {["all", "high", "medium", "low"].map((sev) => (
                    <button
                      key={sev}
                      onClick={() => setSeverityFilter(sev)}
                      className={`cursor-pointer px-2.5 py-1 uppercase text-xs ${
                        severityFilter === sev
                          ? "border border-ink bg-ink font-bold text-paper"
                          : "border border-hairline bg-surface-white text-ink hover:bg-row-hover"
                      }`}
                    >
                      {sev}
                    </button>
                  ))}
                </div>

                {filteredFindings.length === 0 ? (
                  <div className="border border-hairline bg-surface-white p-12 text-center">
                    <p className="font-serif text-neutral-600 italic">No quality findings matching the current filters.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-hairline border border-hairline bg-surface-white">
                    {filteredFindings.map((finding) => (
                      <div key={finding.finding_id} className="p-4 hover:bg-row-hover">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase ${
                                finding.severity === "high"
                                  ? "border border-red-500/30 bg-red-100 text-red-800"
                                  : finding.severity === "medium"
                                    ? "border border-amber-500/30 bg-amber-100 text-amber-800"
                                    : "border border-neutral-300 bg-neutral-100 text-neutral-700"
                              }`}
                            >
                              {finding.severity}
                            </span>
                            <span className="border border-hairline bg-surface-container-low px-1.5 py-0.5 font-mono text-[10px] font-bold text-ink uppercase">
                              {finding.type}
                            </span>
                            <span className="font-mono text-[10px] text-neutral-500">
                              certainty: {finding.certainty}
                            </span>
                          </div>
                        </div>

                        <p className="mt-2 font-sans text-sm font-medium text-ink">
                          {finding.description}
                        </p>

                        {finding.symbols.length > 0 && (
                          <div className="mt-2 flex flex-wrap items-center gap-1.5 pt-1">
                            <span className="font-mono text-[10px] text-neutral-500 uppercase">Impacted:</span>
                            {finding.symbols.map((symKey) => (
                              <span
                                key={symKey}
                                className="border border-hairline bg-paper px-1.5 py-0.5 font-mono text-[11px] text-ink"
                              >
                                {symKey}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Modules View */}
            {activeTab === "modules" && (
              <div className="mt-6 border border-hairline bg-surface-white">
                <div className="grid grid-cols-12 gap-4 border-b border-hairline bg-surface-container-low/40 px-4 py-2.5 font-sans text-[10px] font-bold tracking-widest text-neutral-500 uppercase">
                  <div className="col-span-6">File Path</div>
                  <div className="col-span-2">Language</div>
                  <div className="col-span-4 text-right">Content Hash (SHA-256)</div>
                </div>

                <div className="divide-y divide-hairline">
                  {filteredFiles.map((file) => (
                    <div
                      key={file.file_id}
                      className="grid grid-cols-12 items-center gap-4 px-4 py-3 text-xs hover:bg-row-hover"
                    >
                      <div className="col-span-6 flex items-center gap-2">
                        <FileCode className="size-4 shrink-0 text-neutral-400" />
                        <span className="font-mono font-bold text-ink">{file.path}</span>
                      </div>
                      <div className="col-span-2 font-mono text-[11px] text-neutral-500 uppercase">
                        {file.language}
                      </div>
                      <div className="col-span-4 text-right font-mono text-[11px] text-neutral-400 truncate">
                        {file.content_hash || "—"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tab 4: Symbols View */}
            {activeTab === "symbols" && (
              <div className="mt-6 space-y-4">
                {/* Kind filters */}
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-neutral-500 uppercase text-[10px] font-bold">Kind:</span>
                  {["all", "function", "class", "method", "module"].map((k) => (
                    <button
                      key={k}
                      onClick={() => setSymbolKindFilter(k)}
                      className={`cursor-pointer px-2.5 py-1 uppercase text-xs ${
                        symbolKindFilter === k
                          ? "border border-ink bg-ink font-bold text-paper"
                          : "border border-hairline bg-surface-white text-ink hover:bg-row-hover"
                      }`}
                    >
                      {k}
                    </button>
                  ))}
                </div>

                <div className="border border-hairline bg-surface-white">
                  <div className="grid grid-cols-12 gap-4 border-b border-hairline bg-surface-container-low/40 px-4 py-2.5 font-sans text-[10px] font-bold tracking-widest text-neutral-500 uppercase">
                    <div className="col-span-5">Symbol Name & Key</div>
                    <div className="col-span-2">Kind</div>
                    <div className="col-span-3">Parent Key</div>
                    <div className="col-span-2 text-right">Metrics</div>
                  </div>

                  <div className="divide-y divide-hairline">
                    {filteredSymbols.slice(0, 100).map((sym) => (
                      <div
                        key={sym.stable_key}
                        className="grid grid-cols-12 items-center gap-4 px-4 py-3 text-xs hover:bg-row-hover"
                      >
                        <div className="col-span-5 flex flex-col">
                          <span className="font-mono font-bold text-ink">{sym.name}</span>
                          <span className="font-mono text-[10px] text-neutral-400 break-all">
                            {sym.stable_key}
                          </span>
                        </div>
                        <div className="col-span-2">
                          <span className="border border-hairline bg-surface-container-low px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase text-ink">
                            {sym.kind}
                          </span>
                        </div>
                        <div className="col-span-3 font-mono text-[11px] text-neutral-500 truncate">
                          {sym.parent_key || "—"}
                        </div>
                        <div className="col-span-2 text-right font-mono text-[11px] text-neutral-600">
                          {sym.metrics ? (
                            <span>{Object.entries(sym.metrics).map(([k, v]) => `${k}:${v}`).join(", ")}</span>
                          ) : (
                            "—"
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        ) : null}
      </main>

      <Footer />
      <TweaksPanel />
    </div>
  )
}
