import type { DummyProject } from "@/config/content/dashboard"

interface ProjectRowProps {
  project: DummyProject
  onClick?: (project: DummyProject) => void
}

export function ProjectRow({ project, onClick }: ProjectRowProps) {
  return (
    <article
      onClick={() => onClick?.(project)}
      className="group relative grid cursor-pointer grid-cols-1 items-center gap-2 border-b border-hairline px-3 py-4 text-left transition-colors duration-150 hover:bg-row-hover md:grid-cols-12 md:gap-4 md:px-4"
    >
      {/* Col 1: Name and Diamond */}
      <div className="flex items-center gap-3 md:col-span-4">
        <span className="inline-block font-mono text-xs text-gold transition-transform duration-200 select-none group-hover:rotate-45">
          ◆
        </span>
        <div className="flex flex-col">
          <span className="font-sans text-[17px] font-semibold text-ink transition-colors group-hover:text-accent">
            {project.name}
          </span>
          {project.subtitle && (
            <span className="font-serif text-sm text-neutral-500 italic md:hidden">
              {project.subtitle}
            </span>
          )}
        </div>
      </div>

      {/* Col 2: Timestamp */}
      <div className="font-mono text-[11px] text-neutral-500 md:col-span-2">
        {project.uploadedAt}
      </div>

      {/* Col 3: Graph Metrics */}
      <div className="flex flex-wrap items-center gap-1.5 font-mono text-[12px] text-ink md:col-span-4">
        <span>{project.modules} modules</span>
        <span className="text-neutral-300">·</span>
        <span>{project.edges} edges</span>
        <span className="text-neutral-300">·</span>

        {project.cycles > 0 ? (
          <span
            className="inline-flex items-center gap-1 border border-red-600/30 bg-red-100/50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-red-700"
            title={project.cycleNote || "Circular dependency flagged"}
          >
            <span className="size-1 bg-red-600" />
            {project.cycles} cycle{project.cycles > 1 ? "s" : ""} (flagged)
          </span>
        ) : (
          <span className="text-neutral-500">0 cycles</span>
        )}
      </div>

      {/* Col 4: Size */}
      <div className="font-mono text-[11px] text-neutral-500 md:col-span-1 md:text-right">
        {project.size}
      </div>

      {/* Col 5: Action Arrow */}
      <div className="flex items-center justify-end font-sans text-lg text-ink md:col-span-1">
        <span className="transition-transform duration-150 group-hover:translate-x-1 group-hover:text-accent">
          →
        </span>
      </div>
    </article>
  )
}
