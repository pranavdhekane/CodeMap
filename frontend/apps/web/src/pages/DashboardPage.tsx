import { useState, useMemo } from "react"
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
  initialProjects,
  dashboardContent,
  type DummyProject,
} from "@/config/content/dashboard"

interface DashboardPageProps {
  onNavigateLanding?: () => void
  onSignOut?: () => void
}

export function DashboardPage({
  onNavigateLanding,
  onSignOut,
}: DashboardPageProps) {
  const [projects, setProjects] = useState<DummyProject[]>(initialProjects)
  const [searchQuery, setSearchQuery] = useState("")
  const [activeScope, setActiveScope] = useState<ScopeFilter>("ALL")
  const [activeSort, setActiveSort] = useState<SortCriteria>("RECENT")
  const [isModalOpen, setIsModalOpen] = useState(false)

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

        {filteredAndSortedProjects.length > 0 ? (
          <ProjectList projects={filteredAndSortedProjects} />
        ) : (
          <EmptyState onNewProject={() => setIsModalOpen(true)} />
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
