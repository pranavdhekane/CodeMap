import { ProjectRow } from "./ProjectRow"
import { dashboardContent, type DummyProject } from "@/config/content/dashboard"

interface ProjectListProps {
  projects: DummyProject[]
  onProjectClick?: (project: DummyProject) => void
}

export function ProjectList({ projects, onProjectClick }: ProjectListProps) {
  const { tableHeader, statusTicker } = dashboardContent

  const totalModules = projects.reduce((acc, p) => acc + p.modules, 0)
  const totalSizeBytes = projects.reduce((acc, p) => acc + p.sizeBytes, 0)
  const totalSizeMb = (totalSizeBytes / 1000000).toFixed(2)

  return (
    <div className="mt-2 w-full">
      {/* Table Header (Desktop) */}
      <div className="hidden grid-cols-12 gap-4 border-b border-hairline px-4 py-2.5 text-left font-sans text-[10px] font-bold tracking-widest text-neutral-500 uppercase md:grid">
        <div className="col-span-4">{tableHeader.repository}</div>
        <div className="col-span-2">{tableHeader.timestamp}</div>
        <div className="col-span-4">{tableHeader.metrics}</div>
        <div className="col-span-1 text-right">{tableHeader.size}</div>
        <div className="col-span-1 text-right">{tableHeader.action}</div>
      </div>

      {/* Project Rows */}
      <div className="divide-y divide-hairline">
        {projects.map((project) => (
          <ProjectRow
            key={project.id}
            project={project}
            onClick={onProjectClick}
          />
        ))}
      </div>

      {/* Sub-table Status Ticker */}
      <div className="flex flex-col items-start justify-between gap-2 py-4 font-mono text-[11px] text-neutral-500 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <span className="size-1.5 bg-accent" />
          <span className="tracking-wide">{statusTicker.liveEngine}</span>
        </div>
        <div className="flex items-center gap-4">
          <span>
            {statusTicker.totalParsed}{" "}
            <strong className="font-semibold text-ink">{totalModules}</strong>{" "}
            {statusTicker.modulesSuffix}
          </span>
          <span className="text-neutral-300">/</span>
          <span>
            {statusTicker.cacheLabel}{" "}
            <strong className="font-semibold text-ink">{totalSizeMb}</strong> MB
          </span>
        </div>
      </div>
    </div>
  )
}
