# Verity Technology Stack

| Document control | Detail |
| --- | --- |
| Status | Proposed MVP stack |
| Source of truth | [Product Requirements Document](PRD.md), [Architecture](Architecture.md) |
| Selection principle | Prefer a small, typed, observable platform with managed operations and replaceable AI providers |

## 1. Stack at a glance

| Layer | Selected technology | Responsibility | Decision rationale |
| --- | --- | --- |
| Web application | Next.js with TypeScript | Accessible responsive UI, authenticated app shell, report viewer, upload and audio-capture experience | Next.js provides mature React ergonomics, server rendering where useful, Vercel deployment, and a large ecosystem. TypeScript prevents contract mistakes in a complex evidence UI. |
| Design system | Tailwind CSS, shadcn/ui, Framer Motion | Accessible visual primitives, consistent styling, deliberate motion | Tailwind keeps styling local and token-driven; shadcn/ui supplies editable accessible primitives without a restrictive runtime theme; Framer Motion is limited to meaningful, reduced-motion-aware feedback. |
| HTTP and realtime API | FastAPI | REST API, WebSocket events, validation, OpenAPI contract | FastAPI is asynchronous where I/O matters, strongly aligned with Pydantic schemas, and generates a clear API contract for the web application. |
| Persistence | SQLAlchemy, Alembic | ORM/query boundary and controlled schema migration | SQLAlchemy supports explicit relational modeling and async access; Alembic makes schema changes reviewable, ordered, and reversible where safe. |
| System of record | PostgreSQL | Tenant data, evidence graph, jobs, audits, usage, and reporting | PostgreSQL provides ACID transactions, constraints, JSONB for versioned AI payloads, full-text search, row-level security, backups, and relational reporting in one durable service. |
| Authentication | Google OAuth plus Verity JWT/session tokens | Sign-in and first-party session control | OAuth reduces password-handling risk. Verity-owned short-lived JWT access tokens and rotating server-revocable sessions provide API scalability without surrendering logout/revocation control. |
| AI | OpenAI API, Whisper API, LangChain | LLM planning/evaluation, transcription, provider-neutral orchestration | OpenAI provides the initial language and speech capability. LangChain standardizes prompt/template and structured-output orchestration but is kept behind Verity-owned validation and persistence policy. |
| Optional semantic retrieval | PostgreSQL pgvector first; FAISS only for isolated/local experiments | Retrieve approved long-document fragments | A database-backed index is safer for multi-tenant deletion, access control, and backup. FAISS is valuable for local evaluation but is not a shared source of truth. |
| Async execution | Redis plus Celery | At-least-once task dispatch, bounded retries, scheduling, realtime coordination | Celery makes the worker runtime, retry policy, and operational tooling explicit. PostgreSQL remains authoritative for jobs, idempotency, and outcomes; Redis is never the only durable record. |
| Binary storage | Managed S3-compatible private object storage with KMS-managed encryption | Resume/JD originals, audio, exports, quarantine artifacts | Object storage scales economically and supports short-lived signed access. Bucket policy blocks public access; it avoids putting sensitive large blobs in the primary database. |
| Packaging | Docker and Docker Compose | Reproducible local, CI, and production images | Containers make the API, worker, scheduler, and web runtime explicit. Compose supplies a close local integration environment without turning local setup into cloud-dependent work. |
| Hosting | Vercel and Railway | Next.js delivery; API/realtime/worker processes | Vercel is optimized for Next.js previews and edge delivery. Railway is appropriate for long-running Python, WebSocket, worker, and scheduler processes. |
| CI/CD | GitHub Actions, artifact attestations, and SBOMs | Checks, security scanning, build, deploy promotion | GitHub Actions keeps quality gates alongside the monorepo and integrates naturally with pull requests, Vercel previews, container builds, and deployment credentials. Provenance and SBOMs make a deployed image traceable. |
| Observability | OpenTelemetry, error tracking, structured logs, metrics dashboards | Traces, errors, latency/cost/security signals | AI and queues create non-obvious failure paths; end-to-end traces and redacted structured events are required to operate them responsibly. |

## 2. Frontend decisions

The frontend uses the Next.js App Router with TypeScript in strict mode. It renders the public and authenticated experience, captures audio with browser APIs, streams session events over an authenticated WebSocket, and calls the FastAPI REST contract. Business rules, authorization decisions, prompt logic, and direct data-store access remain server-side.

Tailwind CSS is the styling foundation because it makes responsive, high-contrast, design-token usage reviewable in the component where it matters. shadcn/ui is selected as a source-owned component collection rather than an opaque SaaS UI layer, allowing Verity to meet keyboard, focus, caption, contrast, and screen-reader requirements. Framer Motion is used sparingly for transitions such as session-state changes and report expansion; each motion has a reduced-motion alternative and never conveys information that text does not.

The web app should generate a typed API client from the published OpenAPI description. This prevents frontend/backend contract drift without coupling browser code to Python internals.

## 3. Backend and data decisions

FastAPI hosts versioned REST routes and authenticated WebSocket endpoints. Pydantic schemas define the external contract and validate structured AI output at the boundary; SQLAlchemy models stay internal to the persistence adapter. Alembic is the only approved mechanism for changing production schema. Migrations are reviewed with data-backfill, lock, rollback, and compatibility impact documented.

PostgreSQL is selected over a graph database because the Interview Evidence Graph is a constrained, tenant-owned relational graph: sessions, transcript spans, criteria, claims, drills, and re-tests require foreign keys and transactional updates more than arbitrary graph traversal. JSONB records versioned provider payloads and non-authoritative model metadata only; values used for filtering, authorization, retention, or reporting are normalized columns.

Redis is intentionally not a database of record. It powers task delivery, short-lived locks, rate limits, and multi-instance realtime coordination. A database outbox and idempotency records make Redis outages recoverable and job delivery safe to repeat.

## 4. AI and speech decisions

| Capability | Initial technology | Guardrail |
| --- | --- | --- |
| Document extraction and blueprint planning | OpenAI API through a provider adapter | Structured output must cite stored source-segment IDs; candidate approval gates derived profile facts. |
| Question and follow-up generation | OpenAI API plus versioned LangChain workflow | Only selected rubric criteria and approved role/profile evidence may be used; one question is issued at a time. |
| Speech-to-text | Whisper API | Provisional chunks are clearly marked; final transcript is versioned and candidate-correctable. |
| Evidence extraction | OpenAI API with deterministic span validation | Output names exact transcript IDs/offsets; invalid spans are rejected before evaluation. |
| Rubric evaluation and drills | OpenAI API with structured outputs | Evidence-first, schema-validated, confidence-calibrated, and allowed to abstain; no hiring prediction. |
| Delivery observations | Deterministic audio/transcript metrics | Separate from content scoring; never score accent, pitch, identity, emotion, or personality. |

LangChain is a controlled orchestration dependency, not the domain model. It can compose templates, provider calls, retries, and structured parsers behind a narrow interface. Verity persists its own prompt version, input version, output schema version, provider/model identifier, evaluator policy, configured provider data-use/retention setting, and validation result so that an evaluation is explainable even if a library changes.

The AI adapter contract must support provider timeouts, bounded retries, circuit-breaking, cost metadata, redaction, prompt-injection-safe source labeling, and test doubles. The first provider is OpenAI; a provider change must not require changing interview, evidence, privacy, or report modules. A provider configuration may process candidate data only after vendor privacy/security review, data-retention setting verification, and a recorded approval; the adapter must reject unapproved routes.

## 5. Deployment environments

| Environment | Purpose | Required services | Data rule |
| --- | --- | --- | --- |
| Local | Feature development and deterministic integration tests | Docker Compose web/API/worker/scheduler/PostgreSQL/Redis/object-storage emulator | Synthetic fixtures only; local AI calls are opt-in. |
| Pull-request preview | UI/API contract review | Vercel preview, ephemeral or isolated API environment where needed | No production candidate data or production credentials. |
| Staging | Migration, load, security, and evaluator regression validation | Production-like managed services with dedicated keys | Consented/synthetic test data only; destructive test lifecycle. |
| Production | Candidate-facing service | Vercel, Railway process types, managed PostgreSQL/Redis/storage, observability | Strict tenant isolation, least privilege, backups, retention/deletion lifecycle. |

Production uses custom same-site subdomains such as app and api under the Verity domain. This supports Secure HttpOnly cookie authentication while keeping CORS and CSRF policy narrow. Storage is private; uploads and downloads use time- and object-scoped signatures after an authorization check.

The public API is protected by an edge WAF with request/body limits and DDoS/rate-limit controls. PostgreSQL, Redis, storage administration, and provider credentials are reachable only from workload identities, not from the public web tier. Worker/parser execution has no arbitrary outbound network access and no production database credential beyond its narrowly scoped runtime role.

## 6. CI/CD quality gates

```mermaid
flowchart LR
    Commit["Pull request"] --> Lint["Format, lint, type, and dependency checks"]
    Lint --> Tests["Unit, integration, contract, and E2E tests"]
    Tests --> Security["Secret, dependency, container, and IaC scans"]
    Security --> Eval["AI golden-set and schema regression gates"]
    Eval --> Preview["Vercel preview and review"]
    Preview --> Approve["Required review and protected branch"]
    Approve --> Build["Build immutable image, SBOM, signed provenance"]
    Build --> Stage["Deploy staging and run migration checks"]
    Stage --> Prod["Promote to production"]
    Prod --> Monitor["Monitor, canary/rollback, audit"]
```

The pipeline must fail closed on leaked secrets, breaking migrations, contract incompatibility, critical dependency findings, accessibility regressions, or evaluator-quality regressions. Database migrations run once through a controlled release job using expand, migrate, contract compatibility checks. Production deployment uses immutable image tags, signed provenance, SBOMs, and recorded source revisions so an incident can be traced and rolled back to a known application build. Destructive schema rollback is not automatic; it uses a tested forward fix or restore procedure.

## 7. Security and operations tooling

- **Secrets:** deployment-managed secret store; local developer values in ignored files; automatic rotation plan for OAuth, database, storage, and AI credentials.
- **Monitoring:** OpenTelemetry traces across HTTP, WebSocket, queue, database, and provider spans; metrics for latency, queue depth, cost, quota, and evidence validity.
- **Error tracking:** PII-scrubbed exception reporting with correlation IDs. Raw audio, documents, transcript body, access tokens, and authorization headers are excluded.
- **Security scanning:** dependency, secret, container image, and infrastructure configuration scanning in GitHub Actions.
- **Boundary protection:** edge WAF/rate limits, private storage with explicit deny-public policy, workload identities, parser sandbox limits, and strict egress controls for worker/provider traffic.
- **Backups:** PostgreSQL point-in-time recovery with restore drills; object-storage versioning/lifecycle appropriate to retention policy; backup expiry is documented in deletion status. Before beta, set and test explicit RPO/RTO objectives for database, objects, and deletion/export queues.
- **Audit integrity:** insert-only runtime permissions plus signed, separately retained audit checkpoints; operational searches never need raw candidate content.
- **Feature management:** server-side, auditable rollout flags for new prompts/models/rubrics. A flag cannot bypass consent, authorization, or evaluator quality gates.

## 8. Required operating documentation before beta

The repository layout reserves `docs/adr`, `docs/runbooks`, and `docs/security`; these must contain more than placeholders before candidate data is accepted:

- threat model and data-flow/classification map, including prompt injection and share-link abuse;
- vendor review records for OAuth, AI/speech, storage, telemetry, and error tracking;
- evaluator card defining benchmark provenance, slice sizes, confidence intervals, release gates, and rollback owners;
- runbooks for provider outage, dead-letter replay, security incident, model rollback, export/deletion failure, and restore exercise;
- service-level objectives, alert ownership, capacity assumptions, and tested RPO/RTO targets.

## 9. Deliberate exclusions

The initial stack does not include a separate microservice mesh, Kubernetes, a graph database, a global FAISS index, an event-streaming platform, a browser extension, webcam analytics, or a code-execution sandbox. Each adds operational or ethical complexity without advancing the MVP’s validated learning loop. The architecture retains extension points for future requirements, but no excluded capability is silently introduced through a library or deployment choice.
