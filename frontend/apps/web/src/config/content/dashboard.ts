export interface DummyProject {
  id: string
  name: string
  subtitle?: string
  modules: number
  edges: number
  cycles: number
  cycleNote?: string
  size: string
  sizeBytes: number
  uploadedAt: string
  order: number
}

export const initialProjects: DummyProject[] = [
  {
    id: "1",
    name: "billing-service-v2",
    subtitle: "Python 3.11 · FastAPI",
    modules: 12,
    edges: 34,
    cycles: 1,
    cycleNote: "Detected mutual import cycle: billing.core ↔ billing.invoicing",
    size: "1.2 MB",
    sizeBytes: 1200000,
    uploadedAt: "uploaded 2 hours ago",
    order: 1,
  },
  {
    id: "2",
    name: "auth-gateway-proxy",
    subtitle: "Python 3.10 · gRPC",
    modules: 8,
    edges: 19,
    cycles: 0,
    size: "840 KB",
    sizeBytes: 840000,
    uploadedAt: "uploaded yesterday",
    order: 2,
  },
  {
    id: "3",
    name: "ast-toposort-engine",
    subtitle: "Python 3.12 · Cython Kernel",
    modules: 26,
    edges: 82,
    cycles: 0,
    size: "3.4 MB",
    sizeBytes: 3400000,
    uploadedAt: "uploaded 4 days ago",
    order: 3,
  },
]

export const dashboardContent = {
  nav: {
    brand: "CodeMap",
    dashboardLink: "Dashboard",
    docsLink: "Docs",
    userEmail: "c.babbage@synthetic-ast.org",
    signOutLabel: "Sign out",
  },

  header: {
    indexLabel: "04 / WORKSPACE",
    subIndex: "PARSED REPOSITORIES",
    titleLight: "Your",
    titleBold: "projects.",
    description:
      "Browse your analyzed codebases or upload a new project archive for deterministic AST extraction and cycle detection.",
    newProjectCta: "+ NEW PROJECT",
  },

  filters: {
    searchPlaceholder: "Search projects by name or module...",
    scopeAll: "ALL",
    scopeMine: "MINE",
    sortLabelPrefix: "SORT:",
    sortOptions: [
      { id: "RECENT", label: "RECENT", display: "SORT: RECENT" },
      { id: "NAME_ASC", label: "NAME (A-Z)", display: "SORT: NAME A-Z" },
      { id: "CYCLES", label: "CYCLES COUNT", display: "SORT: CYCLES" },
      { id: "SIZE", label: "SIZE", display: "SORT: SIZE" },
    ] as const,
  },

  tableHeader: {
    repository: "REPOSITORY / SLUG",
    timestamp: "TIMESTAMP",
    metrics: "GRAPH METRICS & TOPOLOGY",
    size: "SIZE",
    action: "ACTION",
  },

  statusTicker: {
    liveEngine: "LOCAL ENGINE RUNNING ON IN-MEMORY WASM",
    totalParsed: "TOTAL PARSED:",
    modulesSuffix: "MODULES",
    cacheLabel: "CACHE:",
  },

  emptyState: {
    title: "No projects yet.",
    description:
      "Upload a Python project zip to parse modules, trace runtime dependencies, and audit cyclic imports strictly on your machine.",
    cta: "+ NEW PROJECT",
    privacyBadge: "NO CODE LEAVES THIS BROWSER CONTEXT",
  },

  uploadModal: {
    tag: "INGESTION ENGINE",
    title: "Upload a project.",
    closeAria: "Close dialog",
    slugLabel: "PROJECT NAME",
    slugPlaceholder: "e.g. billing-service-v2",
    dropzone: {
      idlePrimary: "Drag a",
      idleBadge: ".zip",
      idleSecondary: "here or click to browse",
      constraint: "Max 50 MB · Python projects only",
    },
    fileSelected: {
      metaSuffix: "python source units",
      removeBtn: "✕ REMOVE",
    },
    loading: {
      status: "COMPUTING AST TOPOLOGY",
      verified: "LOCAL SHA-256 VERIFIED",
      logs: [
        "> Ingesting modules...",
        "> Building Directed Acyclic Graph",
        "> Resolving import paths: ./src/*",
        "> Validating AST acyclicity: 0 warnings",
        "> Deterministic cache commit: complete",
      ],
    },
    privacyStrip:
      "$ codemap analyze ./my-project → parsed locally · 0 bytes stored raw",
    cancelBtn: "CANCEL",
    submitIdle: "UPLOAD & ANALYZE",
    submitReady: "START AST PARSING",
    submitLoadingPrefix: "ANALYZING",
  },

  footer: {
    brand: "CodeMap",
    credit: "Team CoCreate · MES IMCC",
    copyright:
      "© 2025 CodeMap Architectural Intelligence. Zero telemetry. Strictly local analysis.",
    links: [
      { label: "Privacy Architecture", href: "#privacy-bar" },
      { label: "Documentation", href: "#docs" },
      { label: "AST Engine", href: "#architecture" },
      { label: "Security Audit", href: "#features" },
      { label: "Changelog", href: "#changelog" },
      { label: "License", href: "#license" },
    ],
    version: "v2.4.1-local-release",
  },
} as const

