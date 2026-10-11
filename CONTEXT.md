# CodeMap: Context

## What it is

A tool that helps a developer understand an unfamiliar Python codebase without sending it to a third party. It parses the project with a rule-based static analysis engine and shows modules, dependencies, call graph, dead code, circular dependencies, complexity hotspots, generated docs and an onboarding report.

## Problem

Inherited projects usually have no documentation. Reading code file by file takes days and repeats for every new team member. Cloud AI tools are not an option for private or client code.

## Team

- Team CoCreate, Group 43, MES IMCC, FY MCA
- Proposal submitted 5 Oct 2026, **pending faculty review**

## Modes

1. **Cloud**: user logs in, uploads a project zip, results saved per user, history, sharing later.
2. **Local**: no login. Run one launcher file; the frontend opens in the browser straight at the project overview.
3. **AI is optional in both**, user's choice, off by default. The rule-based engine is always the base.

> Note: the optional AI toggle is an addition to the submitted proposal (which says "no AI required"). It does not replace the rule-based engine. Mention it to the faculty guide.

## Stack

- Backend: Python, FastAPI
- Engine: pure Python using the built-in `ast` module
- Frontend: React + TypeScript (Vite), graph with Cytoscape.js
- Database: SQLite (local), PostgreSQL (cloud)
- Local run: FastAPI serves the built frontend, a launcher script starts it and opens the browser. During development, the Vite dev server runs alongside FastAPI.

## Architecture (simple)

```
 Local folder / Zip upload
          |
     core/parser  ->  graph (nodes + edges in DB)
                          |
        +-----------------+------------------+
   analyzers          docs/report          ai (optional)
 cycles, dead code,   docstring first,
 complexity, blast    else structural
 radius               summary
        |
   FastAPI (app/)  <--->  React dashboard
   CLI (cli/)
```

The engine in `core/` is shared by the API and the CLI.

## Modules (from the proposal)

| ID | Module | Short description |
|---|---|---|
| M1 | Ingestion and user management | Auth, safe zip upload, temp workspace, store only results |
| M2 | Parser and graph engine | AST to modules/classes/functions/imports/calls, entry points |
| M3 | Analyzers | Cycles (SCC), dead code, complexity, blast radius |
| M4 | Docs and report | Per-function/module docs without AI, onboarding report |
| M5 | Dashboard and CLI | React dashboard, Cytoscape graph, heatmap, history, CLI |

## Weekly plan

Week 1 starts Mon 12 Oct 2026. We build **local mode first** (no login needed), then add cloud on top. Tasks below are to be done in that week.

| Week | Dates | Goal | Tasks |
|---|---|---|---|
| 1 | 12 to 18 Oct | **Setup** | Create repo, add collaborator, branch protection, folder structure, tooling (black, ruff, pytest, eslint, prettier), FastAPI hello world, Vite + React + TS hello world, sample projects in `samples/`, graph data model (nodes, edges) |
| 2 | 19 to 25 Oct | **Parser and graph (M2)** | AST parser (modules, classes, functions, imports, calls), store graph in SQLite, entry point detection, `codemap analyze <path>` CLI prints JSON |
| 3 | 26 Oct to 1 Nov | **Analyzers (M3)** | Circular dependencies (SCC + suggested edge), dead code via reachability, complexity metrics, blast radius, API endpoints that return results |
| 4 | 2 to 8 Nov | **Docs + local dashboard (M4, M5)** | Doc generator (docstring, else structural summary), onboarding report, project overview page, Cytoscape dependency map and call graph, `run_local.py` launcher that opens the browser |
| 5 | 9 to 15 Nov | **Cloud mode (M1)** | Safe zip extraction, temp workspace cleanup, size/count limits, register/login (token auth), PostgreSQL support, saved report history |
| 6 | 16 to 22 Nov | **AI toggle + polish** | Optional AI layer in `core/ai/` (explanations only, off by default, warning before sending code), complexity heatmap, dead code list, filters, folder grouping, report export, AI toggle in UI |

### After week 6

- Weeks 7 to 8: test on 5 open-source Python projects, compare dead code with `vulture` and dependency graphs with `pydeps`, measure precision/recall and analysis time vs project size.
- Then: bug fixes, final documentation and report, demo.
- Deployment is out of scope for now. We will decide later.

## Out of scope for now

- Deployment / hosting
- Languages other than Python
- Mobile app
- Anything beyond the plan above. We will figure out next steps when we get there.
