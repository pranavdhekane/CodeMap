export interface HeroGraphNode {
  id: string
  name: string
  fan: string
  loc: string
  x: number
  y: number
  radius: number
  isHighlighted?: boolean
}

export interface FeatureRowItem {
  name: string
  desc: string
  example: string
  isAccent?: boolean
}

export const landingContent = {
  nav: {
    brand: "CodeMap",
    links: [
      { label: "Features", href: "#features" },
      { label: "How it works", href: "#architecture" },
      { label: "Privacy", href: "#privacy-bar" },
      { label: "Docs", href: "#docs" },
    ],
    signIn: { label: "Sign in", href: "#signin" },
    analyzeCta: { label: "ANALYZE A PROJECT", href: "#analyze" },
  },

  hero: {
    engineTag: "AST ENGINE · PYTHON 3.11+",
    titleLight: "Understand any",
    titleBold: "codebase.",
    description:
      "CodeMap parses Python Abstract Syntax Trees directly on your local machine. Zero code leaves your memory. Interactive dependency maps, dead path detection, and automated onboarding dossiers generated in milliseconds.",
    primaryCta: "ANALYZE A PROJECT",
    secondaryCta: "See how it works →",
    metrics: [
      { label: "TELEMETRY", value: "0.00 Bytes" },
      { label: "EXECUTION", value: "Pure AST" },
      { label: "LATENCY", value: "< 140ms" },
    ],
    graph: {
      headerTag: "LIVE AST PARSE · DIRECTED GRAPH",
      modulesMeta: "6 MODULES / 8 EDGES",
      nodes: [
        {
          id: "router",
          name: "api/v1/router.py",
          fan: "0 in / 2 out",
          loc: "340 lines",
          x: 230,
          y: 60,
          radius: 22,
        },
        {
          id: "user",
          name: "models/user.py",
          fan: "3 in / 2 out",
          loc: "512 lines",
          x: 130,
          y: 150,
          radius: 20,
          isHighlighted: true,
        },
        {
          id: "auth",
          name: "auth.py",
          fan: "2 in / 3 out",
          loc: "289 lines",
          x: 330,
          y: 150,
          radius: 20,
          isHighlighted: true,
        },
        {
          id: "db",
          name: "database.py",
          fan: "2 in / 0 out",
          loc: "140 lines",
          x: 130,
          y: 280,
          radius: 18,
        },
        {
          id: "crypto",
          name: "utils/crypto.py",
          fan: "2 in / 0 out",
          loc: "96 lines",
          x: 330,
          y: 280,
          radius: 18,
        },
        {
          id: "worker",
          name: "worker.py",
          fan: "0 in / 2 out",
          loc: "420 lines",
          x: 230,
          y: 330,
          radius: 18,
        },
      ] as HeroGraphNode[],
      edges: [
        { from: "router", to: "user" },
        { from: "router", to: "auth" },
        { from: "user", to: "db" },
        { from: "auth", to: "crypto" },
        { from: "worker", to: "db" },
        { from: "worker", to: "crypto" },
      ],
      cycleLabel: "CYCLE DETECTED",
      note: "Mutual import between `models/user` & `auth`",
      fix: "Fix: Introduce token_dto.py",
    },
  },

  privacyStrip: {
    command: "codemap analyze ./my-project",
    bullets: [
      "parsed locally via ast",
      "0 bytes uploaded",
      "no outbound connections",
    ],
  },

  architecture: {
    index: "01 / ARCHITECTURAL PIPELINE",
    titleLight: "Start reading ",
    titleBold: "any codebase.",
    stages: [
      {
        stage: "STAGE 01",
        title: "PARSE",
        desc: "AST only. Your code is never executed, sandboxed or evaluated. Pure syntax tree traversal operates over standard library definitions and modern type annotations without bytecode compilation.",
        meta: "Offline syntax parsing",
      },
      {
        stage: "STAGE 02",
        title: "MAP",
        desc: "Bidirectional directed graph of modules, class hierarchies, and execution call chains. Resolves aliased imports, circular paths, and dynamic method dispatches into a single planar matrix.",
        meta: "Topological Cycle Resolution: O(V + E)",
      },
      {
        stage: "STAGE 03",
        title: "UNDERSTAND",
        desc: "Automated architecture dossiers, architectural debt rankings, and instant newcomer onboarding briefs. Surfaces cognitive burden scores across every module before opening your pull request.",
        meta: "Markdown Exporter: Ready for git commit",
      },
    ],
  },

  featureShowcase: {
    badge: "INSPECTION CHAMBER · ZERO ARTIFACT LEAK",
    title: "The inspection chamber.",
    targetFile: "repo/services/billing/checkout.py",
    workspaceTitle: "analysis_workspace // billing_service_v2",
    parserStatus: "PARSER ACTIVE",
    clusterLabel: "CLUSTER: `services.billing.*`",
    cycleAlert: "1 CIRCULAR CYCLE DETECTED",
    suggestedCut:
      "SUGGESTED CUT: Remove direct call from invoice_gen.py to checkout.py",
    cutLink: "View refactoring AST patch →",
    nodeDetails: {
      qualifiedPath: "repo/services/billing/checkout.py",
      couplingStatus: "High Coupling",
      blastRadiusCount: 14,
      directDependents: "9 modules",
      upstreamImports: "5 packages",
      cyclomaticComplexity: "Score: 18 (High)",
      cyclomaticPercentage: "72%",
      recommendation: "Threshold recommendation: ≤ 10 for domain routers.",
      actionButton: "Generate Decoupling Plan",
    },
  },

  featureRows: {
    index: "02 / SURGICAL AUDIT ENGINE",
    title: "System capabilities.",
    description:
      "Deterministic, offline evaluation running against standard AST node visitors. No cloud LLMs hallucinating function signatures.",
    items: [
      {
        name: "Dependency map",
        desc: "Complete visual topological sort of every imported module with live circular cycle resolution.",
        example: "import_graph.resolve_order()",
      },
      {
        name: "Call graph",
        desc: "Cross-file call tracing from HTTP route decorators down through internal service layers to ORM queries.",
        example: 'trace(fn="handle_charge")',
      },
      {
        name: "Dead code detection",
        desc: "Pinpoints unreferenced functions, dangling class declarations, and orphaned configuration dictionaries.",
        example: "24 unused symbols (840 LOC)",
      },
      {
        name: "Circular dependencies",
        desc: "Immediate cycle breaker recommendations calculated via minimum edge cut graph algorithms.",
        example: "cycle: A -> B -> C -> A [CUT B->C]",
        isAccent: true,
      },
      {
        name: "Complexity hotspots",
        desc: "Cognitive complexity heat mapping for targeted refactoring rather than naive LOC metrics.",
        example: "rank_by_cognitive_load(top=10)",
      },
      {
        name: "Onboarding report",
        desc: "Synthesizes system boundaries, entrypoints, and mental models for newly joined staff engineers.",
        example: "output: ONBOARDING.md (14 pages)",
      },
    ] as FeatureRowItem[],
  },

  executionModes: {
    index: "03 / DEPLOYMENT MATRICES",
    titleLight: "Zero trust by design. ",
    titleBold: "Two execution modes.",
    localMode: {
      badge: "STRICT AIR-GAP",
      runtime: "RUNTIME 01",
      title: "LOCAL ENGINE",
      desc: "Single launcher script. Operates without an account, requires no outbound internet connection, uses strictly local SQLite caching in ~/.codemap/.",
      points: [
        "No user authentication or credentials required",
        "No outbound network connections initialized",
        "Instant CLI launch: python scripts/run_local.py",
      ],
      meta: "COST: Free & Open Source",
      cta: "Run local engine →",
    },
    cloudMode: {
      badge: "CLOUD WORKSPACE",
      runtime: "RUNTIME 02",
      title: "CLOUD WORKSPACE",
      desc: "For teams tracking architectural changes. Login, upload project archives, and review visual dependency history with your team.",
      points: [
        "Simple project archive upload & visualization",
        "Historical codebase analysis snapshots",
        "Shareable architecture overviews",
      ],
      meta: "ACCOUNT: Simple sign in",
      cta: "Sign in to cloud →",
    },
    aiDisclosure: {
      title: "Optional AI semantic summaries: OFF by default.",
      desc: "No code or AST representation is ever used for model training or forwarded to third-party endpoints.",
    },
  },

  finalCta: {
    badge: "READY IN SECONDS · AIR-GAPPED VERIFIED",
    titleLight: "Read the code. ",
    titleBold: "Keep it private.",
    description:
      "Analyze your largest Python codebase right now. Zero account creation, zero telemetry packets sent, instant architectural clarity.",
    primaryCta: "ANALYZE A PROJECT",
    secondaryCta: "VIEW DOCUMENTATION",
    command: "python scripts/run_local.py",
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
      { label: "License", href: "#license" },
    ],
    version: "v2.4.1-local-release",
  },
} as const
