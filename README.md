# CodeMap

Privacy-first codebase onboarding and analysis tool. Point it at a Python project and get a dependency map, call graph, dead code, circular dependencies, complexity hotspots, auto-generated docs and an onboarding report.

Team CoCreate (Group 43), MES IMCC, FY MCA.

> Read order for a new session: `README.md` (rules) -> `CONTEXT.md` (what we are building and the plan) -> `STATUS.md` (where we are right now).

---

## 1. Two modes, one engine

| | Local mode | Cloud mode |
|---|---|---|
| Login | None | Yes (token auth) |
| Start | One launcher file, browser opens automatically | Hosted FastAPI + React (later) |
| Input | Local folder path | Zip upload |
| Storage | SQLite | PostgreSQL |
| Code leaves machine | Never | Uploaded, deleted after analysis |
| AI | Optional, user's choice | Optional, user's choice |

AI is **off by default** in both modes. The rule-based engine always works without it. AI only adds extra explanations on top of the results.

---

## 2. File map

```
codemap/
├── README.md            # rules + file map (this file)
├── CONTEXT.md           # project context, architecture, weekly plan
├── STATUS.md            # what is done so far (update every PR)
├── .gitignore
├── backend/
│   ├── core/            # THE ENGINE. Pure Python, no FastAPI imports
│   │   ├── parser/      # AST -> modules, classes, functions, imports, calls
│   │   ├── graph/       # nodes/edges model + DB storage
│   │   ├── analyzers/   # cycles, dead code, complexity, blast radius
│   │   ├── docs/        # documentation + onboarding report generator
│   │   └── ai/          # optional AI layer (off by default)
│   ├── app/             # FastAPI: routes, auth, upload, config, db
│   ├── cli/             # CLI that calls core directly
│   └── tests/
├── frontend/            # Vite + React + TypeScript dashboard
├── scripts/
│   └── run_local.py     # one-file launcher for local mode
└── samples/             # small Python projects used for testing
```

Rule of thumb: `core/` must never import from `app/` or `cli/`. The API and CLI both call `core/`. This is what keeps the engine reusable for both modes.

---

## 3. Git rules (both of us follow these, no exceptions)

1. **Never push to `main`.** Not even a typo fix. Turn on branch protection on GitHub so it is blocked.
2. **Every change goes on its own branch** and is merged through a **Pull Request**.
3. **A teammate reviews and merges the PR.** Do not merge your own PR.
4. Pull the latest `main` before you start a branch and before you open a PR.

### Branch names

```
feat/<short-name>     new feature         feat/ast-parser
fix/<short-name>      bug fix             fix/zip-slip-check
docs/<short-name>     docs only           docs/update-status
chore/<short-name>    setup, tooling      chore/add-ruff
```

### Daily flow

```bash
git checkout main
git pull origin main
git checkout -b feat/ast-parser
# ... work ...
git add <files>
git commit -m "feat(parser): extract function definitions"
git push -u origin feat/ast-parser
# open a PR on GitHub
```

### Commit messages

Format: `type(scope): short message`, lowercase, present tense, under 72 characters.

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

Examples:
- `feat(analyzers): add circular dependency detection`
- `fix(upload): reject files with .. in path`
- `docs(status): mark week 2 parser tasks done`

Commit small and often. One idea per commit. No "wip" or "changes" messages.

### Pull requests

- Small PRs (aim for under ~400 changed lines).
- Title follows the commit format. Description says **what** and **how to test it**.
- Update `STATUS.md` in the same PR if you finished something.
- Tests pass and linters are clean before asking for review.
- Use **squash and merge**, then delete the branch.
- Review within 24 hours. Leave comments, be kind.

### Never commit

- Secrets, `.env` files, API keys, tokens
- Uploaded zips or anyone's private code
- `node_modules/`, `__pycache__/`, `.venv/`, `dist/`, `*.db`

---

## 4. Coding guidelines

**General**
- Keep it simple. Readable beats clever.
- One function does one thing. If it needs a long comment, split it.
- No hardcoded paths, ports or secrets. Use config / environment variables.
- No dead code or commented-out code in PRs (we are building a dead code detector, after all).

**Python (backend, engine, CLI)**
- Python 3.11+. Type hints on all function signatures.
- Format with `black`, lint with `ruff`. Run both before committing.
- Docstring on every public function and class (the tool reads these!).
- Use `logging`, not `print`, except in CLI output.
- `snake_case` for functions and variables, `PascalCase` for classes.
- Every analyzer and parser feature needs a `pytest` test using a sample in `samples/`.
- Analyzers only read the shared graph. They do not parse files themselves.

**TypeScript / React (frontend)**
- TypeScript `strict` mode, no `any` unless justified in a comment.
- Functional components and hooks only.
- `PascalCase` for components, `camelCase` for variables.
- API calls live in one place (`frontend/src/api/`), not scattered in components.
- Format with `prettier`, lint with `eslint`.

**Security (important for a privacy tool)**
- Safe zip extraction: block zip-slip, limit file size and file count.
- Always analyze in a temp workspace and delete it afterwards, even on errors (`try/finally`).
- Never execute or import the user's code. Parse only with `ast`.
- Never log source code contents.

**AI layer rules**
- Off by default. User must switch it on.
- Show a clear warning before any code snippet leaves the machine.
- The app must work fully with it off.

---

## 5. Working together

- Pick one task from the current week in `CONTEXT.md`, create a branch, do it, open a PR.
- Update `STATUS.md` when something is finished.
- Short sync twice a week (15 min): what is done, what is blocked.
- No deployment for now. Everything runs locally during development.
