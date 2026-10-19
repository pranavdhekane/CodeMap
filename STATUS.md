# CodeMap: Status

Last updated: 14 Oct 2026
Current week: **Week 1 (setup)**

Update this file in every PR that finishes something. Keep it short and honest.

## Done

- [x] Scope proposal written and submitted (5 Oct 2026)
- [x] Tech stack decided (Python, FastAPI, React + TS, SQLite / PostgreSQL)
- [x] Two modes decided (cloud and local), AI optional in both
- [x] README, CONTEXT, STATUS drafted
- [x] 6 week plan drafted
- [x] Folder structure and `.gitignore` added
- [x] Frontend scaffolded: Turborepo + npm workspaces, `apps/web` (Vite, React 19, TypeScript strict), `packages/ui` (shadcn/ui, Tailwind v4), eslint and prettier configured
- [x] Stitch design samples (landing, login) and original prompt stored in `frontend/stitch_samples/`
- [x] `frontend/DESIGN.md` written: design rules, product rules, component and animation specs, known gaps in the samples
- [x] Frontend: theme constants (`packages/ui/src/theme/tokens.ts`): colors, fonts, type scale, spacing, motion; mapped to Tailwind v4 and CSS variables
- [x] Frontend: self-hosted fonts (`@fontsource-variable/geist`, `@fontsource/newsreader`, `@fontsource/jetbrains-mono`) for air-gapped offline support
- [x] Frontend: mode config (`apps/web/src/config/mode.ts`) and centralized landing content (`apps/web/src/config/content/landing.ts`)
- [x] Frontend: static landing page ported from Stitch reference adhering to all rules in `frontend/DESIGN.md` (Navbar, Hero with interactive AST graph, Privacy strip with typing simulator, Architecture pipeline, Inverted product inspection chamber, 6 feature rows, Execution modes with AI disclosure, Left-aligned final CTA, Footer with Team CoCreate credit, and Dev Tweaks Panel)
- [x] Frontend: enabled light mode by default across ThemeProvider and components
- [x] Frontend: login page ported from Stitch sample (split 45/55 layout, underline inputs, register/sign-in variants, offline local mode alternative, and right-hand matte black AST dependency network)
- [x] Frontend: client-side routing between Landing and Login pages

## In progress

- [ ] Faculty review of proposal (pending)

## Next up (Week 1)

- [ ] Create GitHub repo and add collaborator
- [ ] Turn on branch protection for `main` (require PR)
- [ ] Backend: FastAPI hello world
- [ ] Frontend: `api/` folder setup and auth backend hookup (when backend is ready)
- [ ] Remove the stray `frontend/.git` folder left by the scaffold (the repo root is the only git repo)
- [ ] Set up black, ruff, pytest (eslint and prettier are done for the frontend)
- [ ] Add 2 to 3 small sample projects in `samples/`
- [ ] Design graph data model (nodes, edges)

## Progress by module

| Module | Status |
|---|---|
| M1 Ingestion and user management | Not started |
| M2 Parser and graph engine | Not started |
| M3 Analyzers | Not started |
| M4 Docs and report | Not started |
| M5 Dashboard and CLI | In progress (frontend scaffold and design rules only) |

## Blockers / questions

- Confirm with the faculty guide that the optional AI toggle is fine alongside the rule-based engine.

## Changelog

- 11 Oct 2026: planning docs created.
- 14 Oct 2026: frontend scaffold, Stitch samples and `frontend/DESIGN.md` added.
- 15 Oct 2026: static landing page ported to React 19 + Tailwind v4 with design tokens and offline fonts.
