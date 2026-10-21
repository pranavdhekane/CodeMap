import { Button } from "@workspace/ui/components/button"
import { dashboardContent } from "@/config/content/dashboard"

interface DashboardHeaderProps {
  onNewProject: () => void
}

export function DashboardHeader({ onNewProject }: DashboardHeaderProps) {
  const { header } = dashboardContent

  return (
    <header className="flex flex-col justify-between gap-6 pb-8 text-left md:flex-row md:items-end md:pb-10">
      <div className="space-y-3">
        <div className="flex items-center gap-2 font-mono text-[11px] tracking-widest text-neutral-500 uppercase">
          <span>{header.indexLabel}</span>
          <span className="text-neutral-300">/</span>
          <span>{header.subIndex}</span>
        </div>
        <h1 className="font-sans text-4xl leading-tight tracking-tight text-ink md:text-[56px]">
          <span
            className="font-light"
            style={{ fontWeight: "var(--headline-weight-contrast, 300)" }}
          >
            {header.titleLight}
          </span>
          <span className="ml-2 font-bold">{header.titleBold}</span>
        </h1>
        <p className="max-w-xl font-serif text-lg leading-relaxed text-neutral-600 italic">
          {header.description}
        </p>
      </div>

      <div>
        <Button
          size="lg"
          onClick={onNewProject}
          className="group cursor-pointer gap-2.5 rounded-[2px] bg-ink px-6 py-3.5 font-sans text-xs font-bold tracking-[0.12em] text-paper uppercase transition-all duration-150 hover:bg-[#2A2A30] active:scale-[0.98]"
        >
          <span>{header.newProjectCta}</span>
          <span className="transition-transform duration-150 group-hover:translate-x-1">
            →
          </span>
        </Button>
      </div>
    </header>
  )
}
