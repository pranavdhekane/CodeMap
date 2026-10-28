import { FolderOpen } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { dashboardContent } from "@/config/content/dashboard"

interface EmptyStateProps {
  onNewProject: () => void
}

export function EmptyState({ onNewProject }: EmptyStateProps) {
  const { emptyState } = dashboardContent

  return (
    <section className="flex w-full flex-col items-center justify-center py-20 text-center md:py-28">
      {/* 32px Folder icon in framed square box */}
      <div className="mb-6 flex size-16 items-center justify-center border border-hairline bg-surface-container-low text-ink">
        <FolderOpen className="size-8 text-ink" strokeWidth={1.5} />
      </div>

      <h2 className="mb-2 font-sans text-2xl font-bold tracking-tight text-ink md:text-3xl">
        {emptyState.title}
      </h2>

      <p className="mb-8 max-w-md font-serif text-base text-neutral-600 italic md:text-lg">
        {emptyState.description}
      </p>

      <Button
        size="lg"
        onClick={onNewProject}
        className="group cursor-pointer gap-3 rounded-[2px] bg-ink px-6 py-3.5 font-sans text-xs font-bold tracking-[0.12em] text-paper uppercase transition-all duration-150 hover:bg-[#2A2A30] active:scale-[0.98]"
      >
        <span>{emptyState.cta}</span>
        <span className="transition-transform duration-150 group-hover:translate-x-1">
          →
        </span>
      </Button>

      <div className="mt-8 flex items-center gap-2 font-mono text-[11px] text-neutral-400">
        <span className="text-gold">◆</span>
        <span>{emptyState.privacyBadge}</span>
      </div>
    </section>
  )
}
