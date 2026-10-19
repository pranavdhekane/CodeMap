export const colors = {
  paper: "#F7F5F0",
  ink: "#0E0E10",
  hairline: "#E3DFD6",
  accent: "#4B2BB5",
  gold: "#B8923A",
  ivory: "#F7F5F0",

  // Surfaces & Hovers
  surfaceWhite: "#FFFFFF",
  surfaceContainer: "#F0EEE9",
  surfaceContainerLow: "#F5F3EE",
  buttonHover: "#2A2A30",
  rowHover: "#EFECE4",

  // Dark Inverted Chamber
  darkSurface: "#0E0E10",
  darkSurfaceElevated: "#161618",
  darkSurfacePanel: "#141417",
  darkHairline: "#2A2A30",
  darkMuted: "#858386",
  darkSubtle: "#47464A",

  // Status & Accents
  error: "#BA1A1A",
  warning: "#EBC164",
} as const

export const fonts = {
  sans: "'Geist Variable', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  serif: "'Newsreader', Georgia, serif",
  mono: "'JetBrains Mono', ui-monospace, SFMono-Regular, monospace",
} as const

export const typography = {
  display: {
    fontFamily: fonts.sans,
    fontSize: "56px",
    lineHeight: "64px",
    letterSpacing: "-0.03em",
    fontWeight: "300",
  },
  displayMobile: {
    fontFamily: fonts.sans,
    fontSize: "36px",
    lineHeight: "44px",
    letterSpacing: "-0.02em",
    fontWeight: "300",
  },
  headlineLg: {
    fontFamily: fonts.sans,
    fontSize: "32px",
    lineHeight: "40px",
    letterSpacing: "-0.02em",
    fontWeight: "700",
  },
  headlineLgMobile: {
    fontFamily: fonts.sans,
    fontSize: "26px",
    lineHeight: "34px",
    letterSpacing: "-0.01em",
    fontWeight: "700",
  },
  headlineMd: {
    fontFamily: fonts.sans,
    fontSize: "22px",
    lineHeight: "28px",
    letterSpacing: "-0.01em",
    fontWeight: "600",
  },
  headlineSm: {
    fontFamily: fonts.sans,
    fontSize: "18px",
    lineHeight: "24px",
    letterSpacing: "0em",
    fontWeight: "600",
  },
  bodyLg: {
    fontFamily: fonts.serif,
    fontSize: "19px",
    lineHeight: "30px",
    letterSpacing: "-0.005em",
    fontWeight: "400",
  },
  bodyMd: {
    fontFamily: fonts.serif,
    fontSize: "16px",
    lineHeight: "26px",
    letterSpacing: "0em",
    fontWeight: "400",
  },
  bodySm: {
    fontFamily: fonts.serif,
    fontSize: "14px",
    lineHeight: "22px",
    letterSpacing: "0em",
    fontWeight: "400",
  },
  codeInline: {
    fontFamily: fonts.mono,
    fontSize: "13px",
    lineHeight: "20px",
    letterSpacing: "-0.01em",
    fontWeight: "400",
  },
  codeBlock: {
    fontFamily: fonts.mono,
    fontSize: "12px",
    lineHeight: "18px",
    letterSpacing: "0em",
    fontWeight: "400",
  },
  labelCaps: {
    fontFamily: fonts.sans,
    fontSize: "11px",
    lineHeight: "14px",
    letterSpacing: "0.12em",
    fontWeight: "700",
  },
  labelMono: {
    fontFamily: fonts.mono,
    fontSize: "11px",
    lineHeight: "16px",
    letterSpacing: "0.04em",
    fontWeight: "500",
  },
} as const

export const spacing = {
  xs: "0.25rem",
  sm: "0.5rem",
  md: "1rem",
  lg: "1.5rem",
  xl: "2.5rem",
  margin: "3rem",
  marginMobile: "1.25rem",
  gutter: "1.5rem",
  gutterMobile: "1rem",
} as const

export const radius = {
  none: "0px",
  sm: "2px",
  interactive: "2px",
  full: "9999px",
} as const

export const motion = {
  durationFast: "150ms",
  durationNormal: "250ms",
  durationSlow: "600ms",
  durationLoopMin: "8000ms",
  easeOutCubic: "cubic-bezier(0.215, 0.61, 0.355, 1)",
  staggerDelay: "60ms",
} as const
