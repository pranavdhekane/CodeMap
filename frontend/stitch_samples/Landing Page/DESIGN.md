---
name: CodeMap
colors:
  surface: '#fbf9f4'
  surface-dim: '#dbdad5'
  surface-bright: '#fbf9f4'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3ee'
  surface-container: '#f0eee9'
  surface-container-high: '#eae8e3'
  surface-container-highest: '#e4e2dd'
  on-surface: '#1b1c19'
  on-surface-variant: '#47464a'
  inverse-surface: '#30312e'
  inverse-on-surface: '#f2f1ec'
  outline: '#77767b'
  outline-variant: '#c8c5ca'
  surface-tint: '#5f5e60'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#1b1b1d'
  on-primary-container: '#858386'
  inverse-primary: '#c8c6c8'
  secondary: '#5f43c9'
  on-secondary: '#ffffff'
  secondary-container: '#785ee4'
  on-secondary-container: '#fffbff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#261a00'
  on-tertiary-container: '#a37f28'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e5e1e4'
  primary-fixed-dim: '#c8c6c8'
  on-primary-fixed: '#1b1b1d'
  on-primary-fixed-variant: '#474649'
  secondary-fixed: '#e6deff'
  secondary-fixed-dim: '#cabeff'
  on-secondary-fixed: '#1d0061'
  on-secondary-fixed-variant: '#4929b3'
  tertiary-fixed: '#ffdf9e'
  tertiary-fixed-dim: '#ebc164'
  on-tertiary-fixed: '#261a00'
  on-tertiary-fixed-variant: '#5b4300'
  background: '#fbf9f4'
  on-background: '#1b1c19'
  surface-variant: '#e4e2dd'
typography:
  display:
    fontFamily: Geist
    fontSize: 56px
    fontWeight: '300'
    lineHeight: 64px
    letterSpacing: -0.03em
  display-mobile:
    fontFamily: Geist
    fontSize: 36px
    fontWeight: '300'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Geist
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0em
  body-lg:
    fontFamily: Newsreader
    fontSize: 19px
    fontWeight: '400'
    lineHeight: 30px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Newsreader
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: 0em
  body-sm:
    fontFamily: Newsreader
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  code-inline:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: -0.01em
  code-block:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  label-caps:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.12em
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.04em
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 3rem
  margin-mobile: 1.25rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system expresses a dual heritage: the surgical rigor of high-velocity developer infrastructure merged with the intellectual restraint of heritage broadsheets and luxury editorial publications. It is engineered specifically for deep codebase navigation and privacy-preserving architectural intelligence. 

The aesthetic eschews modern tech tropes—omitting blurs, drop shadows, saturated gradients, and synthetic pill containers. Instead, the interface operates as a structured, tactile broadsheet printed on heavy off-white stock. Visual hierarchy is established strictly through proportional scale, typographic tension between structural sans-serif headers and literary serifs, and precise 1px rule lines. 

The emotional signature is silent, cerebral, and authoritative. It evokes deliberate study rather than ephemeral scanning, giving engineers the calm focus needed to parse massive multi-tier codebases.

## Colors

The chromatic architecture rests on an ink-on-paper baseline:

- **Base Paper (`#F7F5F0`):** The primary canvas across all viewports. A warm, non-glare off-white that prevents visual fatigue during extended code audits.
- **Deep Ink (`#0E0E10`):** The primary stroke, body ink, and solid button fill. Unforgiving, high-contrast, and dense.
- **Hairline / Rule (`#E3DFD6`):** The single structural border color for panel divisions, data tables, and semantic grouping. Applied uniformly at 1px thickness.
- **Royal Violet (`#4B2BB5`):** The singular active accent. Reserved for interactive focus rings, dependency graph nodes, high-priority AST traversal paths, and active navigation indicators. Never used for decorative fills.
- **Antique Gold (`#B8923A`):** The secondary precision accent. Used exclusively for status indicators, glyphs (e.g., diamonds, flags), security verification seals, and parsing warnings.
- **Inverted Dark (`#0E0E10` Surface / `#F7F5F0` Ink):** Dedicated to technical environments: terminal viewports, shell outputs, AST inspector drawers, and local privacy telemetry panels.

## Typography

The typographic engine uses three distinct voices working in counterpoint:

1. **Structural Headings (`Geist`):** Delivers clean geometry. Display headlines feature contrasting pairings—pairing feather-light `300` weights for framing with authoritative `700` weights for core entity names.
2. **Literary Narrative (`Newsreader`):** Used for analytical documentation, code audit summaries, contextual tooltips, and architectural reports. It provides humanized friction against dense technical data.
3. **Machine Code & Metrics (`JetBrains Mono`):** Applied to AST tokens, Python decorators, memory profiles, file paths, diff markers, and raw data matrices.

Headings and analytical copy are strictly left-aligned. Avoid centered type across all interfaces.

## Layout & Spacing

The layout is built on an architectural 12-column fluid grid locked within a maximum content boundary of 1440px.

- **Desktop (1024px+):** 12 columns with 24px (`1.5rem`) gutters and generous 48px (`3rem`) canvas margins. Left-weighted sidebars house module hierarchies (3 columns), leaving 9 columns for code trees, graphs, and metric readouts.
- **Tablet (768px - 1023px):** 8 columns with 20px gutters and 32px canvas margins. Sidebars collapse into an off-canvas drawer or top drawer toggle.
- **Mobile (<768px):** 4 columns with 16px (`1rem`) gutters and 20px (`1.25rem`) canvas margins. All multi-pane layouts reflow into stacked longitudinal sheets.

Structural alignment follows continuous vertical and horizontal 1px hairlines. Elements do not float; they sit grounded along visible grid lines, creating a structured, sheet-like composition.

## Elevation & Depth

This system operates entirely without shadows, diffusion blurs, and skeuomorphic gradients. The z-axis is strictly planar:

- **Surface Tiers:** Depth is communicated via deliberate value inversion and border demarcations rather than physical height. 
- **Hairline Division:** Panels, floating toolbars, and context popovers sit on `#F7F5F0` or `#FFFFFF` and are bounded by a crisp 1px `#E3DFD6` stroke.
- **Overlay State:** Modals and flyout palettes use a pure 1px stroke perimeter without outer diffusion. When an overlay appears, the background scrim dims with flat `#0E0E10` at 35% opacity—no backdrop filter or gaussian blur applied.
- **Inverted Focus:** Flyouts detailing low-level binary analysis or execution runtimes flip immediately to `#0E0E10` ink with `#F7F5F0` type, establishing clear separation through inverted contrast.

## Shapes

The shape system is strictly architectural and non-rounded.

- **Zero-Radius Standard:** Containers, data cells, code blocks, flyouts, and badges utilize razor-sharp corners (`0px`).
- **Interactive Exception:** Primary buttons and clickable input boxes may carry a maximum border radius of `2px` to prevent visual shearing on subpixel screens, remaining perceptually square.
- **Decorative Elements:** Small geometric glyphs (diamonds `◆`, crosshairs `+`, square bullet points `▪`) serve as bullet markers, breadcrumb dividers, and status indicators.

## Components

### Buttons
- **Primary:** Solid `#0E0E10` fill with `#F7F5F0` text. Maximum `2px` corner radius. Typography is `label-caps` (uppercase, tracking `0.12em`). Padding: 10px vertical by 18px horizontal. No drop shadow. Hover state triggers a subtle background shift to `#2A2A30` with an active state of `#4B2BB5`.
- **Secondary / Ghost:** Transparent background with a 1px `#0E0E10` outline. Black uppercase text. Hover state inverts to full black fill with white text.
- **Icon Action:** 32x32px square container, bordered by 1px `#E3DFD6`, centered 1.5px stroke hairline icon.

### Text Links
- Set in `Newsreader` or `Geist` with a permanent 1px underline positioned with a 3px text offset in `#0E0E10`.
- External and navigational text links conclude with an inline directional arrow (`→` or `↗`). On hover, the arrow shifts 2px right/up and the line turns `#4B2BB5`.

### Chips & Badges
- Unrounded rectangles with 1px `#E3DFD6` borders and `#F7F5F0` backgrounds.
- Height fixed at 22px with 6px horizontal padding.
- Content set in `label-mono` (uppercase). Privacy indicator badges include a 4x4px solid Antique Gold (`#B8923A`) square glyph anchored to the left.

### Form Inputs
- Flat canvas with a 1px `#E3DFD6` bottom border or complete perimeter box. 
- Typeface set to `code-inline` or `body-md`. 
- Focus state switches the border to 1px `#4B2BB5` with no outer glow ring.
- Placeholder text set to `#0E0E10` at 40% opacity.

### Selection Controls (Checkboxes & Radios)
- **Checkbox:** 14x14px sharp square with a 1.5px `#0E0E10` border. Checked state fills solid `#0E0E10` containing a crisp white tick mark.
- **Radio:** 14x14px sharp square rotated 45 degrees into a diamond (`◆`). Active state shows an internal gold `#B8923A` diamond pip.

### Lists & Tables
- Data lists feature 1px `#E3DFD6` horizontal dividers with zero vertical separators.
- Row hover triggers an unbordered background wash of `#EFECE4`.
- Column headers set in `label-caps` with muted ink (`#0E0E10` at 60% opacity).

### Cards & Panels
- Flat panels bounded by a 1px `#E3DFD6` outline. No background elevation, shadows, or rounded corners.
- Header sections separate from content using a single continuous hairline rule.

### Code Viewer & Graph Canvas
- Dedicated analysis panels use the dark inverted surface (`#0E0E10`), lined with faint `rgba(247, 245, 240, 0.1)` grid markers.
- Python AST nodes render with 1.5px stroke vector connections, using `#4B2BB5` to delineate trace routes and `#B8923A` to signal entry/exit points.