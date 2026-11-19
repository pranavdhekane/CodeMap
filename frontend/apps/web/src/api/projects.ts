import { getStoredToken } from "./auth"
import { isLocalMode } from "@/config/mode"
import type { DummyProject } from "@/config/content/dashboard"

export interface ProjectRun {
  run_id: number
  status: string
  scanned_at: string
  commit_hash?: string | null
  files_count: number
  modules_count: number
  symbols_count: number
  edges_count: number
  cycles_count: number
  cycle_note?: string | null
}

export interface ProjectItem {
  project_id: number
  name: string
  description?: string | null
  repo_url?: string | null
  latest_run?: ProjectRun | null
}

const apiBaseUrl = import.meta.env.VITE_API_URL ?? "/api"

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  const token = getStoredToken()
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  } else if (isLocalMode()) {
    headers["Authorization"] = "Bearer local-token"
  }
  return headers
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorBody?.detail ?? `Request failed with status ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function fetchProjects(): Promise<ProjectItem[]> {
  const res = await fetch(`${apiBaseUrl}/projects`, {
    method: "GET",
    headers: authHeaders(),
  })
  const data = await handleResponse<{ projects: ProjectItem[] }>(res)
  return data.projects || []
}

export async function fetchProject(projectId: number): Promise<ProjectItem> {
  const res = await fetch(`${apiBaseUrl}/projects/${projectId}`, {
    method: "GET",
    headers: authHeaders(),
  })
  return handleResponse<ProjectItem>(res)
}

export async function uploadProjectZip(
  file: File,
  name?: string,
  description?: string,
  algorithm = "basic_algo_1"
): Promise<ProjectItem> {
  const formData = new FormData()
  formData.append("file", file)
  if (name?.trim()) {
    formData.append("name", name.trim())
  }
  if (description?.trim()) {
    formData.append("description", description.trim())
  }
  formData.append("algorithm", algorithm)

  const res = await fetch(`${apiBaseUrl}/projects/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  })
  return handleResponse<ProjectItem>(res)
}

export async function seedDemoProject(): Promise<ProjectItem> {
  const res = await fetch(`${apiBaseUrl}/projects/seed-demo`, {
    method: "POST",
    headers: authHeaders(),
  })
  return handleResponse<ProjectItem>(res)
}

export async function deleteProject(projectId: number): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/projects/${projectId}`, {
    method: "DELETE",
    headers: authHeaders(),
  })
  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorBody?.detail ?? `Failed to delete project ${projectId}`)
  }
}

export interface RunFile {
  file_id: number
  path: string
  language: string
  content_hash?: string | null
}

export interface SignatureItem {
  role: "parameter" | "return" | "exception"
  name: string
  type?: string | null
  position: number
}

export interface RunSymbol {
  stable_key: string
  name: string
  kind: "function" | "class" | "method" | "module"
  file?: string
  parent_key?: string | null
  metrics: Record<string, number>
  signature: SignatureItem[]
}

export interface RunEdge {
  source: string
  target: string | null
  kind: "calls" | "imports" | "inherits"
  target_reference?: string | null
  resolution?: string | null
  confidence: number
}

export interface RunFinding {
  finding_id: number
  type: string
  severity: "high" | "medium" | "low"
  certainty: "certain" | "likely" | "uncertain"
  description: string
  symbols: string[]
}

export interface AnalysisRunDetails {
  run_id: number
  project_id: number
  status: string
  commit_hash?: string | null
  scanned_at: string
  files: RunFile[]
  symbols: RunSymbol[]
  edges: RunEdge[]
  findings: RunFinding[]
}

export async function fetchAnalysisRun(runId: number): Promise<AnalysisRunDetails> {
  const res = await fetch(`${apiBaseUrl}/runs/${runId}`, {
    method: "GET",
    headers: authHeaders(),
  })
  return handleResponse<AnalysisRunDetails>(res)
}

export function formatRelativeTime(isoString?: string | null): string {
  if (!isoString) return "recently"
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffSecs = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 1000))
    if (diffSecs < 60) return "just now"
    if (diffSecs < 3600) {
      const mins = Math.floor(diffSecs / 60)
      return `${mins} min${mins > 1 ? "s" : ""} ago`
    }
    if (diffSecs < 86400) {
      const hours = Math.floor(diffSecs / 3600)
      return `${hours} hour${hours > 1 ? "s" : ""} ago`
    }
    const days = Math.floor(diffSecs / 86400)
    return days === 1 ? "yesterday" : `${days} days ago`
  } catch {
    return "recently"
  }
}

export function projectItemToUi(item: ProjectItem, index: number): DummyProject {
  const run = item.latest_run
  const modules = run?.modules_count ?? run?.files_count ?? 0
  const edges = run?.edges_count ?? 0
  const cycles = run?.cycles_count ?? 0
  const cycleNote =
    run?.cycle_note || (cycles > 0 ? `${cycles} circular dependencies flagged` : undefined)

  return {
    id: item.project_id.toString(),
    name: item.name,
    subtitle: item.description || `Python AST · ${run?.status === "done" ? "Analyzed" : run?.status || "Pending"}`,
    modules,
    edges,
    cycles,
    cycleNote,
    size: modules > 0 ? `${Math.round(modules * 1.8 + 12)} KB` : "—",
    sizeBytes: modules * 1800,
    uploadedAt: `scanned ${formatRelativeTime(run?.scanned_at)}`,
    order: index,
  }
}
