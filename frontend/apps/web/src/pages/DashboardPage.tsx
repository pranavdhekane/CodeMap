import { useState, useMemo, useEffect, useCallback } from "react"
import { Navbar } from "@/sections/Navbar/Navbar"
import { Footer } from "@/sections/Footer/Footer"
import { TweaksPanel } from "@/components/TweaksPanel"
import { DashboardHeader } from "@/sections/Dashboard/DashboardHeader"
import {
  FilterBar,
  type ScopeFilter,
  type SortCriteria,
} from "@/sections/Dashboard/FilterBar"
import { ProjectList } from "@/sections/Dashboard/ProjectList"
import { EmptyState } from "@/sections/Dashboard/EmptyState"
import { UploadModal } from "@/sections/Dashboard/UploadModal"
import {
  dashboardContent,
  type DummyProject,
} from "@/config/content/dashboard"
import {
  fetchProjects,
  seedDemoProject,
  deleteProject,
  projectItemToUi,
} from "@/api/projects"

interface DashboardPageProps {
  onNavigateLanding?: () => void
  onNavigateAnalysis?: (projectId: string) => void
  onSignOut?: () => void
}

export function DashboardPage({
  onNavigateLanding,
  onNavigateAnalysis,
  onSignOut,
}: DashboardPageProps) {
  const [projects, setProjects] = useState<DummyProject[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSeeding, setIsSeeding] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [activeScope, setActiveScope] = useState<ScopeFilter>("ALL")
  const [activeSort, setActiveSort] = useState<SortCriteria>("RECENT")
  const [isModalOpen, setIsModalOpen] = useState(false)

  const loadProjects = useCallback(async () => {
    try {
      setIsLoading(true)
      setErrorMessage(null)
      const items = await fetchProjects()
      const mapped = items.map((item, idx) => projectItemToUi(item, idx))
      setProjects(mapped)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load projects"
      setErrorMessage(msg)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadProjects()
  }, [loadProjects])

  const handleSeedDemo = async () => {
    try {
      setIsSeeding(true)
      setErrorMessage(null)
      const seeded = await seedDemoProject()
      const uiProject = projectItemToUi(seeded, 0)
      setProjects((prev) => [uiProject, ...prev])
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load pre-analyzed demo project"
      setErrorMessage(msg)
    } finally {
      setIsSeeding(false)
    }
  }

  const filteredAndSortedProjects = useMemo(() => {
    let list = [...projects]

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.subtitle?.toLowerCase().includes(q) ||
          p.cycleNote?.toLowerCase().includes(q)
      )
    }

    // Sort
    list.sort((a, b) => {
      if (activeSort === "RECENT") return a.order - b.order
      if (activeSort === "NAME_ASC") return a.name.localeCompare(b.name)
      if (activeSort === "CYCLES") return b.cycles - a.cycles
      if (activeSort === "SIZE") return b.sizeBytes - a.sizeBytes
      return 0
    })

    return list
  }, [projects, searchQuery, activeSort])

  const handleProjectCreated = (newProject: DummyProject) => {
    setProjects((prev) => [newProject, ...prev])
    onNavigateAnalysis?.(newProject.id)
  }

  const handleDeleteProject = async (project: DummyProject) => {
    const confirmed = window.confirm(
      `Are you sure you want to remove "${project.name}" from your CodeMap history? This will delete its analysis data.`
    )
    if (!confirmed) return

    try {
      await deleteProject(parseInt(project.id, 10))
      setProjects((prev) => prev.filter((p) => p.id !== project.id))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to remove project"
      alert(msg)
    }
  }

  return (
    <div className="flex min-h-screen flex-col overflow-x-hidden bg-paper font-sans text-ink antialiased selection:bg-accent selection:text-paper">
      <Navbar
        isAuthenticated={true}
        userEmail={dashboardContent.nav.userEmail}
        onNavigateLanding={onNavigateLanding}
        onNavigateDashboard={() => {
          setSearchQuery("")
          setActiveScope("ALL")
          setActiveSort("RECENT")
        }}
        onSignOut={onSignOut || onNavigateLanding}
      />

      <main className="mx-auto flex w-full max-w-[1440px] flex-grow flex-col px-6 py-8 md:px-12 md:py-12">
        <DashboardHeader onNewProject={() => setIsModalOpen(true)} />

        {errorMessage && (
          <div className="mb-6 flex items-center justify-between border border-red-500/30 bg-red-50 px-4 py-3 text-red-800">
            <span className="font-mono text-xs">{errorMessage}</span>
            <button
              onClick={() => void loadProjects()}
              className="cursor-pointer border border-red-400 bg-white px-2.5 py-1 font-mono text-xs font-bold text-red-700 hover:bg-red-50"
            >
              Retry
            </button>
          </div>
        )}

        <FilterBar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          activeScope={activeScope}
          onScopeChange={setActiveScope}
          activeSort={activeSort}
          onSortChange={setActiveSort}
          countAll={filteredAndSortedProjects.length}
          countMine={filteredAndSortedProjects.length}
        />

        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="mb-4 size-6 animate-spin rounded-full border-2 border-ink border-t-transparent" />
            <span className="font-mono text-xs tracking-wider text-neutral-500 uppercase">
              Loading projects from CodeMap engine...
            </span>
          </div>
        ) : filteredAndSortedProjects.length > 0 ? (
          <ProjectList
            projects={filteredAndSortedProjects}
            onProjectClick={(proj) => onNavigateAnalysis?.(proj.id)}
            onProjectDelete={handleDeleteProject}
          />
        ) : (
          <EmptyState
            onNewProject={() => setIsModalOpen(true)}
            onSeedDemo={handleSeedDemo}
            isSeeding={isSeeding}
          />
        )}
      </main>

      {isModalOpen && (
        <UploadModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onProjectCreated={handleProjectCreated}
        />
      )}

      <Footer />
      <TweaksPanel />
    </div>
  )
}
