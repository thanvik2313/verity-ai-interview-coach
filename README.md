# Verity

**Verity** is an evidence-driven AI Interview Coach for SDE, system-design, and AI/ML
candidates. It runs adaptive voice mock interviews and produces an **Interview Evidence
Graph**: every piece of feedback is traceable to a transcript moment, a rubric criterion,
and a versioned evaluation run.

This repository is a monorepo containing the web application, the API/worker backend,
shared packages, tests, infrastructure configuration, and project documentation.

> **Status:** Milestone 1A (repository foundation) complete. Application code
> (Next.js frontend, FastAPI backend, database models, authentication) has not been
> generated yet — see [Current scope](#current-scope) below.

## Documentation

The full product and engineering specification lives under [`docs/`](./docs):

| Document | Path |
| --- | --- |
| Product Requirements | [`docs/architecture/PRD.md`](./docs/architecture/PRD.md) |
| System Architecture | [`docs/architecture/Architecture.md`](./docs/architecture/Architecture.md) |
| Database Design | [`docs/architecture/Database.md`](./docs/architecture/Database.md) |
| Technology Stack | [`docs/architecture/TechStack.md`](./docs/architecture/TechStack.md) |
| Folder Structure | [`docs/architecture/FolderStructure.md`](./docs/architecture/FolderStructure.md) |
| API Contract | [`docs/api/API.md`](./docs/api/API.md) |
| Architecture Decision Records | [`docs/adr/`](./docs/adr) |
| Diagrams | [`docs/diagrams/`](./docs/diagrams) |
| Runbooks (populated at Milestone 5) | [`docs/runbooks/`](./docs/runbooks) |

These documents are the single source of truth for the project. Application code must
not diverge from them without an approved change and, where architectural, an ADR.

## Repository layout

```text
verity/
├── apps/
│   ├── web/          # Next.js application (scaffolded in a later milestone)
│   └── api/           # FastAPI application (scaffolded in a later milestone)
├── packages/
│   ├── api-contract/  # Generated OpenAPI TypeScript client
│   ├── ui/             # Shared UI primitives
│   ├── config/        # Shared lint/format/type/test configuration
│   └── observability/ # Event names, redaction policy, telemetry conventions
├── tests/
│   ├── contract/       # Consumer/provider API contract tests
│   └── fixtures/       # Synthetic or consented, de-identified test assets
├── infra/
│   ├── docker/         # Dockerfiles (added in a later milestone)
│   ├── railway/        # Railway deployment metadata
│   ├── monitoring/     # Dashboards, alerts, tracing configuration
│   └── scripts/        # Operational and CI helper scripts
├── docs/                # Product/engineering documentation (see table above)
└── .github/             # CI workflows and Dependabot configuration
```

Folder ownership is a design boundary: see
[`docs/architecture/FolderStructure.md`](./docs/architecture/FolderStructure.md) for the
full dependency rules between modules, packages, and apps.

## Current scope (Milestone 1A)

This milestone establishes the repository foundation only:

- pnpm workspace and root package management
- Biome for JavaScript/TypeScript lint + format
- Husky, lint-staged, and Commitlint for Git hooks and commit quality
- Docker Compose for local infrastructure services (PostgreSQL, Redis, MinIO)
- GitHub Actions CI skeleton (lint, typecheck, unit tests, integration tests,
  Docker build, security scan — jobs are placeholders until application code exists)
- The full target folder structure, with empty scaffolds for apps and packages

**Not yet included:** the Next.js application, the FastAPI application, database
models, authentication, and Dockerfiles for application services. These arrive in
subsequent Milestone 1 sub-phases.

## Local development (once application code exists)

```bash
# Install JS/TS dependencies across the workspace
pnpm install

# Start local infrastructure (PostgreSQL, Redis, MinIO)
docker compose up -d

# Application-level run instructions are added once apps/web and apps/api exist.
```

## Contributing

Commits must follow [Conventional Commits](https://www.conventionalcommits.org/),
enforced by Commitlint on every commit. Pre-commit hooks run Biome against staged
files via lint-staged. Run `pnpm run check` to lint and format the full workspace
manually.
