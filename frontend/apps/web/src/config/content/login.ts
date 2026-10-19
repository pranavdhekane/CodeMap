export const loginContent = {
  brand: "CodeMap",
  engineSubtitle: "Architectural Engine",
  backToLanding: "Back to landing",

  signIn: {
    titleLight: "Welcome back.",
    titleBold: "Sign in.",
    subtext: "Access your synced architecture diffs and team workspace.",
    submitLabel: "Sign In",
  },

  register: {
    titleLight: "Create account.",
    titleBold: "Get started.",
    subtext:
      "Initialize your private team workspace and architectural diff gates.",
    submitLabel: "Create Workspace",
  },

  fields: {
    fullName: {
      label: "Full Legal Name",
      placeholder: "Ada Lovelace",
    },
    workEmail: {
      label: "Work Email",
      badge: "DOMAIN_VERIFIED",
      placeholder: "architect@domain.internal",
    },
    password: {
      label: "Password",
      placeholder: "Enter passphrase",
      forgotLink: "Forgot password?",
    },
    rememberDaemon: "Remember local daemon token",
    ttl: "TTL 30d",
  },

  modeSwitch: {
    toRegister: "Don't have an account? Create team workspace",
    toSignIn: "Already have an account? Sign in",
  },

  loadingStatus: "verifying_keys [■■■■□□□] 62%",

  errorPreset: {
    code: "err[auth_04]: invalid credentials or air-gapped domain mismatch",
    detail: "Local keyring failed handshake with private boundary cluster.",
  },

  localAlternative: {
    badge: "Local-First Isolation",
    tag: "Air-Gap Engine",
    title: "CONTINUE IN LOCAL MODE, NO LOGIN",
    bullets: [
      "Single binary",
      "No outbound connections",
      "Strict local SQLite cache",
    ],
  },

  canvasRight: {
    statusBadge: "ENCRYPTED AST SESSION · ZERO-TELEMETRY VERIFIED",
    socketsBadge: "SOCKETS: 0 · SANDBOX: JAIL_ROOT",
    topologyHeader: "TOPOLOGY_INSPECTOR: 5 CLUSTERS LOADED",
    cycleAlert: "CYCLE_DETECT: 1 RING FLAGGED",
    cycleBreaker: {
      label: "Cycle breaker suggestion",
      cut: "cut edge #4: detect_cycle.py ↛ local_keyring.py",
    },
    resolutionGauge: "RESOLUTION: 1.4ms (LOCAL C-EXT)",
    terminalTrace: "> libast.resolve_edges(symlink=False, strict=True)",
    terminalStatus: "[OK: 0 EXTERNAL CALLS]",
    terminalCommand: "$ codemap --air-gap --no-telemetry --offline-ast",
    quote: '"Your code never leaves your machine."',
    quoteSubtext:
      "Deterministic client-side AST resolution. Zero external AI endpoints.",
  },

  footer: {
    copyright: "© 2025 CodeMap Architectural Intelligence.",
    links: [
      { label: "Audit Report v3.1", href: "#security" },
      { label: "Keys (PGP)", href: "#pgp" },
    ],
  },
} as const
