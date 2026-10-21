# CodeMap Frontend: Design and Build Rules

Read this before touching anything in `frontend/`. It is the single place for the rules the team set for the UI.
General repo rules (git, commits, PRs, coding style) are in the root `README.md` and always apply.

## 0. Where things live

| What | Where |
|---|---|
| Original Stitch prompt (verbatim) | `stitch_samples/PROMPT.md` |
| Landing page reference (HTML, Tailwind v3 CDN) | `stitch_samples/Landing Page/code.html` |
| Login page reference (HTML, Tailwind v3 CDN) | `stitch_samples/Sign Page/code.html` |
| Stitch's own design system export (tokens + prose) | `stitch_samples/*/DESIGN.md` (both files are identical) |
| App (Vite + React + TS) | `apps/web/` |
| Shared UI package (shadcn primitives, global CSS, tokens) | `packages/ui/` |

`stitch_samples/` is **reference only**. Never import from it, never edit it, never ship it. Port the ideas into React components.

Stack: React 19, Vite, TypeScript (strict), Tailwind CSS v4, shadcn/ui, lucide-react, Turborepo + npm workspaces.
The Stitch samples use the Tailwind **v3 CDN** config. The project uses **v4**, so tokens map into CSS variables and `@theme`, not a `tailwind.config` file.

## 1. Product rules (from the team)

1. CodeMap runs two ways, with **one UI**:
   - **Cloud**: hosted, login required, zip upload, history.
   - **Local**: user downloads the repo, runs the Python launcher, the browser opens the same UI **with no login**, clean and minimal. Everything is processed offline on the machine.
2. The UI must work in both modes. Mode is read from **one place** in the app (a single config module), never checked ad hoc in components. How the mode reaches the frontend (build env or a backend config endpoint) is decided when we build it.
3. Local mode opens straight at the project overview (see `CONTEXT.md`). Login, register and the cloud-only parts of the landing page do not exist in local mode.
4. AI is **off by default** in both modes and shown as OFF in the UI. The app must be fully usable with it off.
5. The landing page content in the Stitch sample is **dummy copy**. It will change with real data later. So all copy and numbers live in content modules (section 3), not inside JSX.
6. Build the frontend in small steps. Do only the step that was asked, then stop.

## 2. Build rules

- Follow the root `README.md` for everything: branches (`feat/`, `fix/`, `docs/`, `chore/`), commit format `type(scope): message`, small PRs, squash and merge, a teammate reviews.
- Update `STATUS.md` in the same PR whenever something is finished.
- TypeScript `strict`, no `any` unless justified in a comment. Functional components and hooks only.
- `PascalCase` components, `camelCase` variables. Format with `prettier`, lint with `eslint`.
- API calls live in **one place**: `apps/web/src/api/`. Never `fetch` inside a component.
- **Modular**: one component per file, small and reusable. Page files only compose sections. Sections only compose components.
- No hardcoded colors, fonts, spacing, copy, paths or ports inside components. Everything comes from tokens or config.
- No dead code, no commented-out code in PRs.
- Package manager is **npm** (the template README mentions pnpm, ignore that). Add shadcn components with `npx shadcn@latest add <name> -c apps/web`. They land in `packages/ui/src/components/`.
- Never commit `node_modules/`, `dist/`, `.env*`, `.turbo/`.

### Proposed layout (confirm at the structure step)

```
apps/web/src/
  api/          all backend calls
  config/       mode.ts, content/ (landing.ts, login.ts, ...)
  pages/        LandingPage, LoginPage, (later) Overview ...
  sections/     one folder per page section (Hero, PrivacyStrip, ...)
  components/   app-level reusable pieces (Logo, GraphCanvas, SectionHeader, ...)
  hooks/        useReducedMotion, useInView, ...
  lib/          small helpers
packages/ui/src/
  components/   shadcn primitives, restyled to this design
  theme/        tokens.ts (single source of truth, see section 3)
  styles/       globals.css
```

## 3. Theme constants: one place, one-click change

All fonts and colors are defined **once** and used everywhere. Changing the brand should mean editing one file.

- One source of truth: `packages/ui/src/theme/tokens.ts` (to be created in the next step). It holds the palette, font families, type scale, spacing, radius and motion timings listed below.
- Tokens are exposed to Tailwind through CSS variables and `@theme` in `globals.css`, so utilities like `bg-paper`, `text-ink`, `border-hairline`, `text-accent` work. The same tokens are available in TypeScript for SVG graphs and the tweaks panel.
- Components use semantic names (`paper`, `ink`, `hairline`, `accent`, `gold`), never hex values.
- shadcn's own variables (`--background`, `--primary`, `--ring`, ...) are **mapped to these tokens**, not left at the template defaults.
- The tweaks panel (section 7) changes the same variables at runtime. It must not keep its own copy of the colors.

### Colors

| Token | Value | Use |
|---|---|---|
| paper | `#F7F5F0` | page background |
| ink | `#0E0E10` | text, solid buttons, dark sections |
| hairline | `#E3DFD6` | every 1px divider and border |
| accent | `#4B2BB5` | **only** graph highlights, link hover, focus rings, one key moment per screen |
| gold | `#B8923A` | **only** one tiny detail (diamond mark, live status dot) |
| ivory | `#F7F5F0` | text on the dark inverted sections |

Stitch also exported hover and surface shades used by the samples: `#2A2A30` (button hover), `#EFECE4` (row hover), `#FFFFFF` (panel surface), `#161618` / `#141417` (dark panel surfaces), `#2A2A30` (dark hairline). Keep them as named tokens too.
The full Material-style token list is in `stitch_samples/*/DESIGN.md`. Only bring over what a component actually needs.

Rules: ONE accent. No other colors. Dark inverted section is allowed **once** on the landing page.

### Typography

| Role | Font | Notes |
|---|---|---|
| Headings, labels, buttons | Geist | huge headlines mix a **light (300)** line and a **bold (700)** line |
| Body | Newsreader (serif) | refined, readable |
| Code, paths, function names, numbers | JetBrains Mono | everything technical and every number |

Type scale (from Stitch): display 56/64 light, display-mobile 36/44 light, headline-lg 32/40 bold, headline-lg-mobile 26/34 bold, headline-md 22/28 semibold, headline-sm 18/24 semibold, body-lg 19/30, body-md 16/26, body-sm 14/22, code-inline 13/20, code-block 12/18, label-caps 11/14 bold uppercase tracking 0.12em, label-mono 11/16 medium tracking 0.04em.
The headline light weight is a variable (the sample's tweaks slider changes it). Keep it a token.
Fonts load through `@fontsource` packages (offline-safe), **not** Google Fonts links, because local mode must work with no network.

### Spacing, grid, shape

- Strict **12-column grid**, max width **1440px**. Desktop (1024+): 12 cols, 24px gutter, 48px margin. Tablet (768 to 1023): 8 cols, 20px gutter, 32px margin. Mobile (<768): 4 cols, 16px gutter, 20px margin.
- Spacing tokens: xs 0.25rem, sm 0.5rem, md 1rem, lg 1.5rem, xl 2.5rem.
- Left-aligned layouts. Lots of white space.
- Radius: **2px max** on buttons and inputs. Containers, cards, badges, code blocks are `0`. Fully round only for tiny status dots.
- Icons: thin line, **1.5px stroke** only (use `lucide-react` with `strokeWidth={1.5}`). The logo is a small node-and-edge glyph.

### Avoid (hard no)

Gradients, glassmorphism and backdrop blur, glow, drop shadows, emoji, sparkle icons, stock illustrations, rounded pastel cards, centered-everything layouts, fake testimonials, fake logos. Depth comes from 1px hairlines and value inversion only.

## 4. Component rules

Build once, reuse on every screen and in the rest of the app.

- **Primary button**: solid ink, paper text, 2px radius, small uppercase label (label-caps), padding about 10px by 18px. Hover `#2A2A30`, active accent. A subtle arrow slides right on hover.
- **Secondary button**: transparent, 1px ink outline, uppercase. Hover inverts to solid ink.
- **Text link**: permanent 1px underline with 3px offset, ends with an arrow (`→` or `↗`). Hover turns accent and the underline grows from the left.
- **Input**: underline-style only (no boxes), 1px hairline bottom border. Focus: underline expands and turns accent, no glow ring. Error: inline message in mono.
- **Checkbox**: 14px sharp square, 1.5px ink border, filled ink with white tick when checked.
- **Chip/badge**: unrounded, 1px hairline border, 22px high, mono uppercase. Privacy badges carry a small gold square or diamond.
- **Card/panel**: flat, 1px hairline border, no radius, no shadow. Header separated by a hairline.
- **List/table rows**: 1px hairline dividers, no vertical lines, hover wash `#EFECE4`.
- **Section header**: small mono index label (like `01 / TITLE`) above a two-weight headline.
- **Graph canvas**: 1.5px strokes. Accent for trace and cycle routes, gold for entry/exit points. Dark variant uses the inverted surface with a faint dot grid.
- Overlays: flat ink scrim at 35% opacity, no blur.

## 5. Landing page (cloud mode) spec

Single scroll, in this order:

1. **Nav**: node-and-edge logo mark, links (Features, How it works, Privacy, Docs), right side "Sign in" text link and black "Analyze a project" button.
2. **Hero**: two-weight headline ("Understand any" light / "codebase." bold), one serif sentence, black CTA "Analyze a project", text link "See how it works →", large animated graph on the right.
3. **Privacy strip**: one mono line, e.g. `$ codemap analyze ./my-project   → parsed locally · 0 bytes uploaded`, small gold dot.
4. **"Start reading any codebase."** Three columns, thin icons: Parse (AST only, code never executed), Map (graph of modules, classes, calls), Understand (docs and onboarding report). Serif body.
5. **Feature showcase** (the one dark section): product window with a dependency graph and a side panel for the selected node (path in mono, "blast radius: 14"). A circular dependency in accent with a note "Suggested edge to remove".
6. **Six feature rows** divided by hairlines: Dependency map, Call graph, Dead code, Circular dependencies, Complexity hotspots, Onboarding report. Each has a one-line description and a tiny mono example.
7. **Two modes side by side**: Local (no login, one launcher file, SQLite) and Cloud (login, zip upload, history). Optional AI shown as **OFF by default**.
8. **Final CTA**: "Read the code." light / "Keep it private." bold, with the black button.
9. **Footer**: logo, **"Team CoCreate · MES IMCC"**, muted serif links, small uppercase legal links.

Desktop 1440px plus a mobile layout. Tagline: "Understand any codebase. Nothing leaves your machine."

## 6. Login page (cloud mode) spec

- Split layout: left **45%** form on paper, right **55%** ink panel with a slowly moving graph and one quiet mono line, "Your code never leaves your machine."
- Form: logo, headline "Welcome back." light / "Sign in." bold, email and password (underline inputs, show/hide toggle), black "Sign in" button, "Create account" link, "Forgot password" link.
- Below a hairline: "Prefer to stay offline? Continue in local mode, no login →" as a secondary outlined button.
- States: **focus** (accent underline), **error** (inline mono message), **loading** (button label becomes a progress line), **register** variant.
- The Stitch sample has a "STATE:" switcher bar at the top of the form. That is a design-review tool. Do **not** ship it. Build the states as real component states.
- Desktop plus a mobile layout (panels stack).

## 7. Animation rules

Respect `prefers-reduced-motion`: show the final static state. Nothing loops faster than **8 seconds** per cycle. Nothing flashy.

- **Hero graph**: nodes fade in one by one, edges draw along their path (`stroke-dashoffset`), one cycle edge turns accent and pulses **once**, then nodes drift very slowly. Hovering a node highlights its neighbors and dims the rest.
- **Headline**: light line fades up first, then the bold line reveals with a masked slide-up (about 600ms, ease-out cubic).
- **Scroll reveals**: sections fade up 16px with a 60ms stagger. Hairlines draw left to right as they enter.
- **Privacy strip**: the terminal line types out **once**, then a blinking cursor.
- **Dark product window**: on scroll into view the graph assembles, a node gets selected, the side panel slides in, the blast radius count ticks up.
- **Buttons/links**: arrow slide on hover, underline grows from the left.
- **Login**: right-hand graph moves slowly, input underline expands on focus.
- Keep motion timings as tokens (duration, easing, stagger) next to the other theme constants.

## 8. Tweaks panel

A small panel with: accent color picker, headline weight slider, motion on/off toggle, dark/light toggle. It drives the same theme variables as section 3 and the same reduced-motion flag as section 7.
Open question: ship it as a design-review tool (dev only) or as a real user setting. Decide when we build it. Until then treat it as dev only.

## 9. Known gaps in the Stitch samples (do not copy blindly)

The samples are a visual reference. Where they disagree with the rules above or with the project, the rules win.

**Breaks the design rules**
- Login uses `backdrop-blur`, a glow `box-shadow` on the gold pip, `shadow-2xl` on the tweaks panel, a `animate-pulse` dot and a dot-grid background. No blur, glow or shadows.
- Landing "Final CTA" is centered. Keep it left-aligned.
- Landing typing animation loops (types, deletes, retypes). Rule: types out once.
- Cycle edge pulses forever every 2s. Rule: pulse once, nothing under 8s per loop.
- Login icons use the Material Symbols font. Rule: 1.5px line icons (lucide).
- Login's Tailwind config has `rounded-lg` and `xl` at 8px and 12px. Landing's config (2px) is the correct one.
- Hover and focus states in both samples use the Material `secondary` `#5f43c9`, not the real accent `#4B2BB5`.

**Missing from the samples (to build)**
- Hero graph draw-in sequence, neighbor highlight and dim on hover, masked headline reveal, scroll reveals, hairline draw-in, product-window assemble sequence, `prefers-reduced-motion` handling, real mobile layouts, and a proper dark/light toggle (the landing sample only has a quick simulation).

**Copy that is wrong for this project (dummy for now, fix when real data arrives)**
- "Parses in your browser" and "client-side AST resolution": parsing happens in the Python engine on the machine, not in the browser.
- "Zero network sockets": local mode serves the UI from localhost, so say "no outbound connections" instead.
- "libcst", "Python 3.9 to 3.13": the engine uses the built-in `ast` module, and the README targets Python 3.11+.
- "Single binary", "brew install", `curl ... | bash`, "UNIX domain sockets": local mode is `scripts/run_local.py` and a browser tab.
- Cloud card talks about enterprise teams, CI/CD gates, SOC2 Type II, zero-knowledge encryption: none of this exists. Cloud mode is login, zip upload, history.
- All numbers (450k LOC/sec, 140ms, 42MB, 14 pages, 24 unused symbols) are invented.
- Footer says "(c) 2025 CodeMap Architectural Intelligence". Brief says "Team CoCreate · MES IMCC".
- Login fields "Work Email / DOMAIN_VERIFIED", "Remember local daemon token", "Create team workspace", "Full Legal Name", footer links "Audit Report v3.1" and "Keys (PGP)": placeholder only.
- Nav, hero and footer link to anchors like `#analyze`, `#docs`. Real routes come later.
