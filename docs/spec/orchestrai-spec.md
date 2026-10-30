# ORCHESTRAI — Frozen Implementation Specification

| Field | Value |
|---|---|
| Project | OrchestrAI — Agentic AI-Powered Technology Intelligence Platform |
| Document | `docs/spec/orchestrai-spec.md` |
| Status | **FROZEN v1.0** |
| Date | 2026-09-06 |
| Companion artifacts | `erd.dbml` (database schema), `agent-graph.mmd` (LangGraph workflow) |
| Change control | Architectural changes require a written change note appended to section 26 and explicit approval. Do not silently alter this specification. |

---

## 1. Purpose and Non-Negotiable Definition

OrchestrAI automates **technology research and strategic decision support**. It is **not a generic chatbot**. The value proposition is the composition:

```
Multi-source Knowledge + RAG + Agentic AI + Multi-Agent Collaboration
+ Technology Intelligence + Strategic Decision Support
```

**MVP definition (frozen):** the following complete workflow must run reliably before scope is expanded:

```
User submits research question
  → Orchestrator understands intent
  → System retrieves relevant documents (RAG)
  → RAG creates grounded context
  → Multiple agents analyze evidence
  → Trend/insight generation
  → Report generation
  → Dashboard displays results and sources
```

---

## 2. Frozen Technology Stack

| Layer | Technology | Version note |
|---|---|---|
| Frontend | React + TypeScript | React 18, Vite |
| Styling | Tailwind CSS | v3 |
| Charts | Recharts | |
| Backend | Python + FastAPI | Python 3.12, FastAPI 0.115+ |
| Data models / validation | Pydantic v2 | |
| Agent orchestration | LangGraph | |
| LLM provider | Claude family (Anthropic) | Haiku / Sonnet / Opus via API |
| RAG | LangChain (components) + retrieval code | only where useful; do not wrap everything |
| Embeddings | local sentence-transformers model | see decision D2 — Anthropic exposes no embeddings API |
| Vector store | Qdrant | |
| OLTP database | PostgreSQL | v16 |
| Cache / queue / rate-limit store | Redis | v7 |
| Auth | JWT + Argon2id | |
| Migrations | Alembic | |
| Jobs | RQ (Redis Queue) | background ingestion + research runs |
| Deployment | Docker Compose; K8s-compatible later | |
| Version control | Git / GitHub | |

**Stack rule:** nothing may be added without a requirement that justifies it. Nothing in the frozen stack may be replaced silently.

---

## 3. Consistency Review (contradictions found in the brief, resolved here)

| # | Contradiction / gap | Resolution |
|---|---|---|
| R1 | §6 lists `document_metadata`; §20 lists `document_chunks`. | Metadata lives on `documents` (source-level columns) and `document_chunks` (chunk-level metadata + `vector_id`). No separate `document_metadata` table. Qdrant payloads denormalize the same metadata for filtering. |
| R2 | "Embedding model" required but Claude provides no embeddings endpoint. | Local embedding model (default `BAAI/bge-base-en-v1.5`, 768 dim, cosine), loaded in backend/worker. Model + dimension are configuration and stored on documents/collection so a hosted embedder can be swapped later without schema change. (D2) |
| R3 | Research runs are LLM+multi-agent flows that can take minutes; the API section implies a plain request/response. | Research execution is **asynchronous**: `POST /api/research` accepts the job and returns `202`, the worker executes the LangGraph, and clients poll status. Document ingestion is likewise async for files. (D1) |
| R4 | §6 lists two different storage tables for agent data; §21 lists `research_id` while the schema uses `research_queries`. | Single canonical identifier: `research_query_id`. A "research run" is a row in `research_queries` (one row per submitted query execution). |
| R5 | §4/§6 mention multiple external sources (news, patents) while §29 excludes "dozens of external APIs" and "autonomous web crawling". | MVP sources: user-uploaded files + **structured corpus import** (JSON/CSV records for papers/patents/reports/news). Live third-party source connectors are post-MVP. |
| R6 | §8 "no uncontrolled agent-to-agent communication" but agents need shared results. | All agent I/O flows through the typed LangGraph `ResearchState`; no free-form agent-to-agent calls. |
| R7 | "Hybrid retrieval" box implies BM25+vector in MVP. | MVP retrieval = semantic (vector) + Qdrant payload filters (metadata). Sparse/BM25 hybrid is a documented post-MVP extension. (D6) |
| R8 | Optional worker service (§25) vs. need for async research. | `worker` service is **required** in the default Compose stack because ingestion and research run off the request thread. |

---

## 4. Functional Requirements (FR)

| ID | Requirement |
|---|---|
| FR-01 | Users register, log in, and receive JWTs. Protected endpoints reject anonymous and expired requests. |
| FR-02 | Every user-owned entity carries `user_id`; all reads/writes are scoped to the authenticated user (multi-user, **single-tenant**). |
| FR-03 | Documents can be uploaded (PDF, DOCX, TXT, MD) and validated (size, MIME, magic bytes). |
| FR-04 | Structured corpus records (papers/patents/reports/news) can be imported via JSON/CSV. |
| FR-05 | Ingested documents pass through: validate → extract → clean → normalize → metadata extraction → chunk → embed → store (Qdrant vector + PostgreSQL metadata). |
| FR-06 | Ingestion progress is observable per document (`ingestion_status` state machine). |
| FR-07 | Each chunk stores traceability metadata (document, source type, title, authors, year, page, section, URL) enabling source-grounded answers. |
| FR-08 | A research query is classified into a query type (literature search, comparison, trend analysis, research summary, report generation, decision support). |
| FR-09 | Research execution runs the LangGraph workflow asynchronously and reports stage-level status. |
| FR-10 | Retrieval respects metadata filters (source type, year range, project scope, user scope) and returns scored chunks with source references. |
| FR-11 | RAG answers are grounded in retrieved chunks; generated text cites sources; uncited claims are suppressed per policy. |
| FR-12 | The Orchestrator selects which agents run based on intent and knowledge availability (conditional routing). |
| FR-13 | Agents: Retrieval, Analysis, Trend, Report, Orchestrator/Supervisor. Inputs/outputs are explicitly typed. |
| FR-14 | Model routing is complexity-aware (Haiku / Sonnet / Opus), configurable, not hard-coded per agent. |
| FR-15 | Trend engine computes a transparent, explainable trend score from interpretable signals (activity, recency, growth, source diversity, relations). |
| FR-16 | Intelligence layer produces trends, insights, opportunities, risks and evidence-backed recommendations with confidence. |
| FR-17 | Structured research reports follow the 10-section report template and are stored/versioned. |
| FR-18 | Dashboard aggregates projects, recent activity, trends, insights, recommendations, source statistics, and reports. |
| FR-19 | Every agent execution is logged (`agent_runs`), including model used, latency, status, and errors. |
| FR-20 | Users can give feedback (thumbs/rating/comment) on reports and research runs. |
| FR-21 | All external providers fail gracefully: retry → fallback → controlled error; never leak internals. |

## 5. Non-Functional Requirements (NFR)

| ID | Requirement |
|---|---|
| NFR-01 | Modular: components swappable via interfaces (embeddings, LLM provider, vector store, queue). |
| NFR-02 | Maintainable + testable: unit tests, API tests, RAG/agent evaluation harness, E2E acceptance script. |
| NFR-03 | Security: JWT auth, Argon2id hashing, input validation, authorization on every endpoint, env-based secrets, CORS allow-list, rate limiting, file validation, no secrets in frontend, safe logging. |
| NFR-04 | Observability: JSON application logs, request logs (request_id, latency, user), agent execution logs, research stage status, error logs. |
| NFR-05 | Availability of dependent services surfaced via `/api/health/live` and `/api/health/ready`. |
| NFR-06 | Deterministic where possible: retrieval fusion, trend scoring, and routing logic are deterministic; LLM steps are the only stochastic parts and are logged. |
| NFR-07 | Performance budget: simple research runs target < 60 s wall time on demo hardware; status polling must never block the API. |
| NFR-08 | Source attribution is preserved end-to-end; every insight/report section references chunk/document IDs. |
| NFR-09 | Deployable via `docker compose up` from a fresh clone with `.env.example`. |
| NFR-10 | Cost-aware: model router prefers the cheapest model that satisfies task complexity; LLM failures cascade down the fallback chain. |

---

## 6. Logical Architecture

```
User
  ↓
React + TypeScript frontend (Vite + Tailwind + Recharts)
  ↓  REST/JSON (JWT)
FastAPI backend (api layer → services → domain)
  ↓
Authentication / authorization layer
  ↓
Query processing (intent detection + query type + plan)
  ↓
Model router (complexity-aware Claude selection)
  ↓
LangGraph orchestrator (supervisor, shared state)
  ↓
RAG retrieval (Qdrant) ── PostgreSQL metadata
  ↓
Specialized agents (Retrieval / Analysis / Trend / Report)
  ↓
Knowledge synthesis + Technology Intelligence (trends/insights/recommendations)
  ↓
Report generation → storage
  ↓
Dashboard / Reports (frontend)
```

Two execution surfaces share the codebase:

- **API process** (uvicorn): auth, CRUD, upload validation, job enqueue, status/read endpoints, health.
- **Worker process** (RQ): ingestion jobs (`ingest_document`, `import_corpus`) and research jobs (`run_research`), each executing the LangGraph.

### 6.1 Component dependency map

```
frontend ──REST──▶ backend/api ──▶ services
                                        │
                          ┌─────────────┼──────────────┬───────────────────┐
                          ▼             ▼              ▼                   ▼
                   core/config     database/      rag/ (retrieval,    ingestion/
                   (settings,      (session,      embeddings,         (extract,
                    logging,        repos)         context)            chunk, embed)
                    security)                                        agents/
                                    models/                          (graph,
                   schemas/         (SQLAlchemy    services/jobs       nodes,
                    (Pydantic)       models)       (RQ queue)          state)
                          │             │              │
                          └─────────────┼──────────────┘
                                        ▼
                              Prompts (versioned) ─▶ LLM router ─▶ Anthropic API
                                        │
                    Qdrant ◀────────────┴──▶ PostgreSQL ◀── Redis ◀── (cache, queue, rate limits)
```

Rules: `api` never touches models/tables directly; `agents` never talk to the DB directly (they read state + call retrieval service); prompts live in `app/prompts/` and are versioned; all infra access goes through ports in `services/` so components are replaceable.

---

## 7. Repository Layout

```
orchestrai/                     (repo root)
├── frontend/                   React + TS + Tailwind (Vite)
│   ├── src/
│   │   ├── api/                typed API client, auth header
│   │   ├── components/         shared UI + charts
│   │   ├── pages/              /login /register /dashboard /research
│   │   │                       /research/new /research/history /knowledge
│   │   │                       /trends /insights /reports /settings
│   │   ├── hooks/              useResearchStatus (polling) etc.
│   │   ├── types/              mirrors backend schemas
│   │   └── App.tsx
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py             FastAPI app factory, middleware, exception handlers
│   │   ├── api/                routers: auth, users, projects, research,
│   │   │                       documents, search, rag, agents, trends,
│   │   │                       insights, reports, dashboard, feedback, health
│   │   ├── core/               config, logging, security (JWT, hashing),
│   │   │                       errors, rate limits
│   │   ├── models/             SQLAlchemy models
│   │   ├── schemas/            Pydantic request/response schemas
│   │   ├── database/           engine, session, base
│   │   ├── services/           auth, documents, ingestion, research,
│   │   │                       retrieval (RAG), intelligence (trend score,
│   │   │                       insights, recommendations), reports, jobs (RQ)
│   │   ├── agents/             langgraph graph, state, nodes, router
│   │   ├── rag/                chunking, embeddings, context builder,
│   │   │                       vector store client (Qdrant)
│   │   ├── ingestion/          extractors, cleaners, normalizers,
│   │   │                       metadata extraction, corpus import
│   │   └── prompts/            versioned prompt files
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── evaluation/         rag_eval, agent_eval, e2e_acceptance
├── docs/spec/
│   ├── orchestrai-spec.md      this document
│   ├── erd.dbml                database schema
│   └── agent-graph.mmd         LangGraph workflow diagrams
├── docker-compose.yml
├── .env.example
├── README.md
└── .gitignore
```

---

## 8. Data Model

Full schema: `erd.dbml`. Summary of the 10 entities (normalized; no extra tables):

| Entity | Purpose | Key relationships |
|---|---|---|
| `users` | accounts | 1:N projects, documents, research_queries, trends, insights, reports, feedback |
| `research_projects` | user grouping of research | N:1 users; 1:N research_queries |
| `research_queries` | one submitted query + one execution | N:1 users; N:1 projects (nullable); 1:N agent_runs, insights, trends, reports, feedback |
| `documents` | source-level metadata + ingestion state | N:1 users; 1:N document_chunks |
| `document_chunks` | chunk-level metadata incl. `vector_id` → Qdrant point | N:1 documents |
| `insights` | findings/trends/opportunities/recommendations | N:1 research_queries, N:1 users, project nullable |
| `trends` | technology trend with explainable score | N:1 research_queries (nullable → ad-hoc trend runs), N:1 users |
| `reports` | structured reports (versioned) | N:1 research_queries |
| `agent_runs` | execution log of every graph node | N:1 research_queries |
| `feedback` | user feedback on runs/reports | N:1 users, research_queries nullable, reports nullable |

Conventions:

- PK `uuid` default `gen_random_uuid()`.
- Timestamps `created_at`/`updated_at` (`now()`), `started_at`/`completed_at` where relevant.
- Every user-owned table indexes `user_id`; `research_queries` indexes `(user_id, status)`, `(project_id)`; `agent_runs` indexes `(research_query_id, agent_name)` and `(research_query_id, started_at)`.
- Enumerations implemented as CHECK-constrained text in DBML (`enum` blocks) mapped to Python `StrEnum`.
- `evidence`/`signal_scores`/`metadata`/`sections` stored as `jsonb`.

### 8.1 Ingestion status state machine (documents.ingestion_status)

```
received → validated → extracted → cleaned → normalized → chunked → embedded → indexed
        ↘ failed (terminal, error_message set)         (retry: reset to received)
```

### 8.2 Research query status (research_queries.status)

```
queued → running → completed
                  ↘ failed     (error + stage recorded; retry creates a new run)
                  ↘ cancelled  (user-initiated stop, MVP optional)
```

---

## 9. Data Ingestion

### 9.1 Sources (MVP)

1. User-uploaded documents (PDF/DOCX/TXT/MD).
2. Structured corpus import (JSON/CSV): records for research papers, patents, technical reports, and news with `text` or retrievable `url` (non-crawlable URLs stored but not fetched in MVP).

### 9.2 Pipeline stages

```
Source → Collection → Validation → Text Extraction → Cleaning → Normalization
      → Metadata Extraction → Chunking → Embedding Generation → Qdrant + PostgreSQL
```

| Stage | Behavior |
|---|---|
| Collection | Multipart upload (files) or parsed import records. |
| Validation | size ≤ 25 MB (config), MIME allow-list, magic-byte sniff, SHA-256 checksum; reject duplicates by `(user_id, source_type, external_id)` for imports and by checksum for uploads. |
| Extraction | PDF (PyMuPDF), DOCX (python-docx), TXT/MD (direct). OCR is out of MVP scope (R6 note). |
| Cleaning | strip control chars, normalize whitespace/Unicode, remove repeated boilerplate headers where detectable. |
| Normalization | lower/trim identifiers, normalize date→year, authors → list, language tag. |
| Metadata extraction | title, authors, year, URL, source type, section/page from extraction layout where available. |
| Chunking | recursive character splitter, default chunk 1000 chars / overlap 200 (config), heading-aware for DOCX/MD; attach `page_number`, `section`, `chunk_index`. |
| Embedding | local model (D2), batched (32), idempotent re-run. |
| Storage | write `document_chunks` rows (incl. `vector_id`), upsert points to Qdrant with full payload; mark `indexed`. |

### 9.3 Jobs

- `POST /api/documents/upload` → creates `documents` row → enqueues `ingest_document`.
- `POST /api/documents/import` → validates records → enqueues `import_corpus`.
- Document deletion is two-phase: delete Qdrant points (by `vector_id`s) then delete rows.

---

## 10. RAG Architecture

```
User query → Query understanding → Query embedding → Qdrant retrieval
  → Relevant chunks → Metadata filtering → Context construction
  → LLM reasoning → Grounded response → Source references
```

### 10.1 Retrieval pipeline (deterministic parts)

1. **Query understanding** (Haiku): normalize the query, extract filter intents (source types, year range, entity names).
2. **Query expansion** (Haiku, optional): produce up to 3 search facets from the query (e.g., sub-topics).
3. **Embed** each facet with the configured embedding model.
4. **Search** Qdrant with payload filter: `user_id = <user>` AND optional `source_type IN (...)` AND `publication_year >= / <= ...`, optional project scope via document tags.
5. **Fusion**: dedupe chunk hits across facets (Reciprocal Rank Fusion), diversity cap per document (default ≤ 3 chunks/doc).
6. **Threshold**: drop chunks below configurable `min_score` (default 0.25); if zero chunks remain → **insufficient-knowledge route**.
7. Return chunks with `document_id`, `chunk_id`, `title`, `source_type`, `authors`, `year`, `section`, `page`, `url`, `score`.

### 10.2 Context construction

- Build ordered context blocks (`#docId` headers + content), truncate to a token budget (default 12k tokens, config).
- Include a machine-readable evidence manifest `[chunk_id → {document, title, year, url}]` that flows into agents and the report references.

### 10.3 Grounding rules

- System prompt instructs the model to answer **only from context** and cite `[dN]`.
- A deterministic post-check verifies each citation exists in the evidence manifest; invalid citations are stripped and logged.
- If the context is insufficient for the query, the run completes with `insufficient_knowledge=true` and the UI shows a "no evidence / upload more sources" state rather than an LLM hallucination.

---

## 11. Model Router

Router input: `{task_family, complexity_level, estimated_input_tokens, query_type, agent}`.
Router output: `{model_id, fallback_chain, budget_note}`. **Agents request a capability; the router picks the model.** Nothing is hard-wired to a single agent permanently; defaults are configuration.

### 11.1 Complexity levels

| Level | Meaning | Default model | Typical tasks |
|---|---|---|---|
| L1 simple | classification, extraction, short generation | Claude Haiku | intent detection, query type, metadata extraction, query expansion, routing labels |
| L2 standard | analytical reasoning over provided evidence | Claude Sonnet | retrieval reasoning, analysis, comparisons, trend interpretation, most synthesis |
| L3 complex | long-horizon synthesis, strategic judgment | Claude Opus | final synthesis, strategic recommendations, complex comparative reasoning, long report generation |

### 11.2 Deterministic selection keys

`level = max(rubric(task_family), rubric(input_size), rubric(query_type))`, where the rubric is a config table (JSON/YAML). Example entries: `comparison → L2`, `decision_support → L3`, `report_generation → L3` when `report_length=long` else `L2`; context tokens > 40k pushes one level up. Users may pass `model_preference` (one of `auto|haiku|sonnet|opus`) per research request; `auto` is default.

### 11.3 Failure policy (LLM)

Retry with exponential backoff (max 3) on transient errors → on persistent failure step down the fallback chain (Opus→Sonnet→Haiku for read-mostly nodes) → if all fail, mark node failed, notify orchestrator, run completes `failed` with a controlled message. Router configuration and effective choice for every node are recorded in `agent_runs.model_used`.

---

## 12. Agent Specifications

Every agent: typed input → deterministic workflow → typed output; state mutations only through the shared `ResearchState`; each node wrapped by the same runner that writes `agent_runs` and applies retry/fallback.

### 12.1 Orchestrator / Supervisor Agent
- **Responsibilities:** understand intent; classify query type; build research plan (which agents, which filters, budget); route via graph edges; maintain shared state; handle failures; decide completion or the insufficient-knowledge route.
- **Input:** `ResearchState` (query, user context).
- **Output:** `plan {query_type, required_agents[], filters, top_k, depth}` appended to state.

### 12.2 Retrieval Agent
- **Responsibilities:** formulate/expand retrieval queries; run retrieval service; apply filters; return source-grounded context + evidence manifest.
- **Input:** `{query, query_type, filters, top_k, min_score}`.
- **Output:** `{retrieved_chunks[], evidence_manifest, diagnostics}`.

### 12.3 Analysis Agent
- **Responsibilities:** analyze retrieved evidence; summarize/extract findings; compare technologies; identify relationships; produce synthesized sub-analyses with citations.
- **Input:** `{query, retrieved_chunks, mode: summarize|compare|extract|decision, focus}`.
- **Output:** `{findings[], analyses[{type,title,body,evidence[],confidence}]}`.

### 12.4 Trend Agent
- **Responsibilities:** consume deterministic trend signals (section 14) plus evidence; identify emerging technologies; interpret momentum; explain *why* a technology is trending using the signal components.
- **Input:** `{query, retrieved_chunks, signal_components}`.
- **Output:** `{trends[{technology, score, components{}, interpretation, evidence[], momentum}]}`.

### 12.5 Report Agent
- **Responsibilities:** organize findings/trends into the 10-section template; produce the executive summary; generate recommendations (evidence-linked); assemble references.
- **Input:** `{query, findings, trends, analyses, evidence_manifest, recommendation_mode}`.
- **Output:** `{report: {sections[], recommendations[], references[]}}` (JSON persisted; markdown rendered for export).

### 12.6 Agent execution log contract (`agent_runs`)

`research_query_id, agent_name, agent_version, task, input(jsonb), retrieved_sources(jsonb), output(jsonb), model_used, status, error_message, retry_count, started_at, finished_at, latency_ms`.

---

## 13. LangGraph Workflow

Reference diagram: `agent-graph.mmd`.

```
START → Query Understanding → Model Router → Orchestrator (plan)
  → [conditional] → Retrieval Agent ─┐
  → [conditional] → Analysis Agent   ├→ Synthesis → Report Agent → Persist → END
  → [conditional] → Trend Agent ─────┘
```

Rules:
- No uncontrolled agent-to-agent communication; all data passes through `ResearchState`.
- Conditional edges: Orchestrator decides which of Retrieval/Analysis/Trend are required from `plan.required_agents` (see §12.1 routing table below); Report runs when the result must be a report/summary/decision (all query types).
- Any node may route to a **failure handling** edge (retry → fallback model → controlled failure) and back to the orchestrator.
- After synthesis the Orchestrator reviews completeness; if evidence is missing it may route back to Retrieval (bounded, ≤ 1 re-iteration in MVP) or close the run with `insufficient_knowledge`.

### 13.1 ResearchState (typed, shared)

```
research_query_id, user_id, project_id
query, query_type, intent, plan
filters, retrieved_chunks[], evidence_manifest
analyses[], trends[], signal_components{}
synthesis, report, recommendations[]
status, current_stage, errors[], agent_run_log[], insufficient_knowledge
```

### 13.2 Query-type → agents routing table (default, deterministic)

| Query type | Required agents | Report mode |
|---|---|---|
| `literature_search` | Retrieval, Analysis (organize) | structured list + summary |
| `research_summary` | Retrieval, Analysis | summary |
| `comparison` | Retrieval, Analysis (comparative) | comparative analysis |
| `trend_analysis` | Retrieval, Analysis, Trend | trends + interpretation |
| `report_generation` | Retrieval, Analysis, Trend (optional), full pipeline | full 10-section report |
| `decision_support` | Retrieval, Analysis, Trend (optional) | decision support + recommendations |
| unknown/empty corpus | → insufficient-knowledge close | message |

---

## 14. Technology Intelligence Engine

Retrieved evidence → agent analysis → knowledge synthesis → trends/insights/opportunities → recommendations → technology intelligence. The LLM raw response is **not** the intelligence layer.

### 14.1 Trend score (transparent, deterministic core)

For each candidate technology `T` over the retrieved/aggregated corpus window:

```
score(T) = 100 * ( w_a*S_activity + w_r*S_recency + w_g*S_growth + w_d*S_diversity + w_x*S_relations )
```

| Signal | Definition (deterministic) | Default weight |
|---|---|---|
| `S_activity` | min–max normalized count of documents mentioning T in window | 0.25 |
| `S_recency` | recency-weighted publication count (exp decay, half-life 12 months) | 0.25 |
| `S_growth` | normalized slope of per-period document counts (linear regression over time buckets, sigmoid-scaled) | 0.30 |
| `S_diversity` | fraction of distinct source types (papers/patents/reports/news) among T’s evidence | 0.10 |
| `S_relations` | normalized co-occurrence of T with other tracked technologies across chunks | 0.10 |

Interpretation buckets: `0–25 = emerging/niche`, `25–50 = developing`, `50–75 = growing`, `75–100 = hot`. Weights configurable via env (`TREND_WEIGHT_*`). Component sub-scores and the underlying counts are stored in `trends.signal_scores` so the UI can explain *why* (e.g., "high recency, strong growth in 2025–2026 papers").

The Trend Agent **interprets** these signals against evidence (and may add L3 synthesis for strategic framing), but never fabricates numbers; numbers come from the engine.

### 14.2 Insights & recommendations

- Insight categories: `finding | trend | opportunity | risk | comparison | recommendation`.
- Every insight stores `evidence[]` (chunk/document IDs), `confidence` and rationale.
- Recommendation record (per §15 example): technology, activity levels (research/recent/knowledge/complexity), suitability statement, confidence, supporting sources.
- `confidence` combines: evidence coverage (fraction of requested facets with sources), evidence count, source diversity, recency, and model self-rationale — components stored in `insights.metadata` for transparency.

---

## 15. Report Structure (frozen template)

1. Research question
2. Executive summary
3. Key findings
4. Technology landscape
5. Research trends
6. Comparative analysis (when applicable)
7. Opportunities
8. Risks / limitations
9. Strategic recommendations
10. References (numbered, mapped to evidence manifest)

Reports persist as structured JSON (`reports.content.sections[]`) + rendered markdown. Versioning: re-generation creates a new `reports` row with incremented `version` for the same `research_query_id`.

---

## 16. API Contracts

Base path: `/api` (configurable constant `API_PREFIX`). Auth: `Authorization: Bearer <JWT>` on all routes except `/api/auth/register`, `/api/auth/login`, `/api/health/*`. Validation: Pydantic schemas; errors: 422. Errors follow one envelope:

```json
{ "error": { "code": "validation_error|not_found|...", "message": "human text",
             "details": {} , "request_id": "..." } }
```

Common codes: `validation_error(422)`, `unauthorized(401)`, `forbidden(403)`, `not_found(404)`, `conflict(409)`, `unsupported_media(415)`, `file_too_large(413)`, `rate_limited(429)`, `service_unavailable(503)`, `internal_error(500)`.
List endpoints return `{items:[], total, page, page_size}`.

### 16.1 Endpoint reference

| Method & path | Auth | Request (body/query) | Success | Purpose |
|---|---|---|---|---|
| `POST /api/auth/register` | no | `{email,password,full_name}` | 201 `{user}` | create account (Argon2id hash) |
| `POST /api/auth/login` | no | `{email,password}` | 200 `{access_token, token_type}` | issue JWT |
| `GET /api/auth/me` | yes | – | 200 `{user}` | current user |
| `GET /api/users/me` | yes | – | 200 profile | alias used by settings |
| `PATCH /api/users/me` | yes | `{full_name?,password?}` | 200 | update profile |
| `POST /api/projects` | yes | `{title,description?}` | 201 | create project |
| `GET /api/projects` | yes | pagination | 200 list | list own projects |
| `GET /api/projects/{id}` | yes | – | 200 | detail (ownership enforced) |
| `PATCH/DELETE /api/projects/{id}` | yes | body / – | 200/204 | update/delete own project |
| `POST /api/research` | yes | `{project_id?,query,query_type_hint?,model_preference?,filters?,notify?}` | **202** `{research_query_id,status}` | enqueue research run |
| `GET /api/research` | yes | `{project_id?,page,page_size,status?}` | 200 list | history |
| `GET /api/research/{id}` | yes | – | 200 full result | query + output + agents |
| `GET /api/research/{id}/status` | yes | – | 200 `{status,current_stage,insufficient_knowledge,error}` | poll |
| `GET /api/research/{id}/agent-runs` | yes | – | 200 list | per-node logs |
| `GET /api/research/{id}/report` | yes | – | 200 latest report | convenience |
| `POST /api/documents/upload` | yes | multipart file + `{title?,source_type}` | 202 `{document_id}` | enqueue ingestion |
| `POST /api/documents/import` | yes | `{source_type, records[]}` | 202 | structured corpus import |
| `GET /api/documents` | yes | `{status?,source_type?,page}` | 200 list | knowledge base |
| `GET /api/documents/{id}` | yes | – | 200 detail + status | inspect |
| `GET /api/documents/{id}/chunks` | yes | `{page}` | 200 list | chunk metadata |
| `DELETE /api/documents/{id}` | yes | – | 204 | delete doc + vectors |
| `POST /api/documents/{id}/ingest` | yes | – | 202 | re-run ingestion |
| `GET /api/search` | yes | `{q,filters,top_k}` | 200 chunks | semantic search UI + eval |
| `POST /api/rag/retrieve` | yes | `{query,filters,top_k}` | 200 chunks | retrieval service (tests/agents) |
| `POST /api/rag/generate` | yes | `{query,top_k?,filters?}` | 200 `{answer,sources}` | direct grounded answer (tests) |
| `GET /api/agents` | yes | – | 200 registry | agent/config inventory |
| `GET /api/agents/runs` | yes | `{research_id?,page}` | 200 | execution logs |
| `GET /api/trends` | yes | `{project_id?,query_id?,top_n}` | 200 list | stored trends |
| `GET /api/trends/{id}` | yes | – | 200 | trend + components + evidence |
| `POST /api/trends/analyze` | yes | `{project_id?,source_filters?,top_n}` | 202 | ad-hoc trend run over corpus |
| `GET /api/insights` | yes | `{project_id?,query_id?,category?}` | 200 | insights |
| `GET /api/reports` | yes | `{project_id?,query_id?,page}` | 200 | reports |
| `GET /api/reports/{id}` | yes | – | 200 report JSON | view |
| `POST /api/reports/{query_id}/regenerate` | yes | `{model_preference?}` | 202 | new version |
| `GET /api/dashboard/overview` | yes | `{project_id?}` | 200 overview | dashboard aggregates |
| `POST /api/feedback` | yes | `{research_query_id?,report_id?,feedback_type,rating?,comment?}` | 201 | store feedback |
| `GET /api/health/live` | no | – | 200 | liveness |
| `GET /api/health/ready` | no | – | 200/503 | deps (pg/qdrant/redis/llm config) |

Dashboard overview payload: user/project counts (documents by source type, chunk counts, projects, recent research runs with statuses, latest trends top-N, latest insights, latest reports, pending/failed ingestion).

Rate limiting: auth endpoints 10 req/min/IP; research POST 5 req/min/user; default API 120 req/min/user (Redis-backed).

---

## 17. Authentication & Security

- Registration: email + Argon2id password hash; email uniqueness enforced; basic email format validation (no email delivery in MVP).
- Login issues JWT (HS256, PyJWT), `sub=user_id`, `exp` default 12 h (config); secret ≥ 32 random bytes from env.
- Every user-owned endpoint filters by `user_id` (server-side, never trusted from client IDs).
- CORS allow-list from `CORS_ORIGINS` env; security headers middleware; request body size caps at proxy/API; upload validation (§9.1) incl. magic bytes; filenames sanitized; documents stored outside static web root.
- No LLM/vector/DB secrets in frontend or its build; `.env` only in backend; `.env.example` committed, real `.env` git-ignored.
- Logging redacts tokens, passwords, and document contents at DEBUG where relevant.
- Prompt-injection hygiene: retrieved text is untrusted data — delimited with explicit system/user framing, citation post-check, and output treated as data by the UI.

---

## 18. Observability

- JSON logs (structlog) with `request_id`, `user_id`, `event`, `level`, `latency_ms`.
- Request middleware logs every API call (method, path, status, duration, request_id).
- Agent execution rows (`agent_runs`) give per-node model, duration, status, error.
- Research run exposes `status`, `current_stage`, `started_at`, `completed_at`, `error`.
- `/api/health/live` + `/api/health/ready` (checks postgres, qdrant, redis; logs degraded states).

---

## 19. Deployment (Docker Compose)

Services (compose file lives at repo root; Kubernetes-compatible: stateless API/worker, env-driven config, persistent volumes for PG/Qdrant, no host-specifics):

| Service | Image/command | Notes |
|---|---|---|
| `frontend` | node build → nginx static | serves SPA, proxies `/api` |
| `backend` | `uvicorn app.main:app` | API process |
| `worker` | `rq worker` (same image) | required — research + ingestion jobs |
| `postgres` | postgres:16-alpine | volume; healthcheck |
| `qdrant` | qdrant/qdrant | volume; healthcheck |
| `redis` | redis:7-alpine | volume; healthcheck |

Compose runs Alembic migrations on backend start. `.env.example` documents all variables.

---

## 20. Configuration (`backend/.env`, mirrored in `.env.example`)

| Key | Default | Notes |
|---|---|---|
| `DATABASE_URL` | – | postgres DSN |
| `QDRANT_URL` | `http://qdrant:6333` | |
| `REDIS_URL` | `redis://redis:6379/0` | cache + queue + rate limits |
| `JWT_SECRET` | – | ≥32 bytes |
| `JWT_EXPIRES_MINUTES` | `720` | |
| `CORS_ORIGINS` | `http://localhost:5173` | |
| `ANTHROPIC_API_KEY` | – | backend only |
| `LLM_MODEL_HAIKU/SONNET/OPUS` | `claude-...-haiku/sonnet/opus` | current API aliases |
| `LLM_FALLBACK_CHAIN` | opus→sonnet→haiku | read-mostly nodes step down |
| `MODEL_ROUTER_CONFIG` | – | path to routing rubric JSON |
| `EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | local; dim 768 |
| `EMBEDDING_DIM` | `768` | must match collection |
| `CHUNK_SIZE/CHUNK_OVERLAP` | `1000 / 200` | chars |
| `RAG_MIN_SCORE` | `0.25` | retrieval floor |
| `RAG_CONTEXT_TOKEN_BUDGET` | `12000` | |
| `RAG_TOP_K` | `20` | default fetch |
| `TREND_WEIGHT_*` | 0.25/0.25/0.30/0.10/0.10 | §14 |
| `RATE_LIMIT_*` | §16 defaults | |
| `UPLOAD_MAX_MB` | `25` | |
| `LOG_LEVEL` | `INFO` | JSON logs |

---

## 21. Development Order (phases with exit criteria)

| Phase | Scope | Exit criterion |
|---|---|---|
| P1 Foundation | repo, Compose, FastAPI app factory, config/logging/health, Alembic + all tables, React shell + routing + Tailwind, auth (register/login/JWT/me), users/projects CRUD | register → login → call protected endpoint; compose healthy |
| P2 Knowledge system | upload/import, validation, extraction, cleaning, chunking, embeddings, Qdrant collection + payload indexes, ingestion status, documents APIs | upload PDF → status `indexed` → chunk rows + Qdrant points exist; `GET /api/search` returns chunks with metadata |
| P3 RAG | retrieval service, filters, RRF, context builder, grounded generation, citation post-check, `rag/*` endpoints | grounded answer with valid sources; eval: hit-rate + MRR reported |
| P4 Agents | router, prompts, state, nodes, graph, supervisor, `agent_runs` logging, research job + polling | `POST /api/research` completes; per-node rows in `agent_runs`; stage polling accurate |
| P5 Technology Intelligence | trend engine, insight synthesis, recommendations, ad-hoc trend analyze | explainable trend scores with component breakdown and evidence |
| P6 Dashboard | research UI (new/history/status), knowledge page, trends/insights/reports views, overview, charts | §28 MVP workflow visible end-to-end in UI |
| P7 Testing | unit, integration, RAG eval, agent eval, E2E acceptance | §22 acceptance criteria green |
| P8 Deployment | compose hardening, env, README, production notes | fresh clone `docker compose up` runs demo |

Phases are sequential; do not start P7/P8 hardening before the MVP workflow (P1–P6) is reliable.

---

## 22. Testing & Acceptance Criteria

Automation: pytest + httpx (API), pytest-asyncio, per-service containers (compose up deps for integration), seeded mini-corpus for evaluation.

| Area | Tests | Acceptance |
|---|---|---|
| A Auth | register/login/me, wrong creds, expired token, missing header | unauthorized rejected with 401; correct flows 200/201 |
| B Ingestion | upload valid/invalid/size/mime, import, status transitions | doc reaches `indexed`; failures recorded; no partial vectors |
| C Retrieval | seeded corpus queries; filters; metadata preserved | relevant top-k; `document_id/chunk_id` present; filter respected |
| D RAG | grounded answer; citation validity; empty-corpus case | ≥ threshold citations map to evidence; no fabricated sources; `insufficient_knowledge` handled |
| E Multi-agent | graph runs for each query type; logging rows; forced node failure | correct agent subset per routing table; state shared; failure → retry/fallback/controlled error |
| F Intelligence | trend score determinism & component math; insight evidence non-empty | same corpus → same score; every insight cites evidence |
| G Reporting | report JSON template completeness; versioning | 10 sections; references match evidence manifest |
| H Dashboard | overview payload; UI renders MVP workflow | all aggregates returned and rendered |
| I System | full E2E: seed → upload/import → research → report → dashboard | MVP workflow green in CI script |

Evaluation metrics (P7): retrieval hit-rate@5, MRR@10; faithfulness via LLM-as-judge (Claude) on sampled runs; agent latency/cost per node; research success rate on the demo corpus.

---

## 23. Assumptions

- A1 English-language primary corpus/UI text (embedding model is multilingual-capable; not relied upon in MVP).
- A2 Demo corpus will be assembled from user uploads + structured imports (papers/patents/news/reports with accessible text). No crawling.
- A3 Anthropic API reachable from backend/worker at runtime; keys held server-side only.
- A4 Default local embedding model can be downloaded once at image build/first start; offline demo viable after that.
- A5 Single-node demo hardware can run Postgres + Qdrant + Redis + API + worker + local embedder.
- A6 LLM quality gates (thresholds, weights) need calibration against the demo corpus in P5–P7.

## 24. Decisions Log (frozen)

| ID | Decision |
|---|---|
| D1 | Research + ingestion are asynchronous (RQ jobs, worker required, 202 + polling). |
| D2 | Embeddings = local `BAAI/bge-base-en-v1.5` (768d, cosine) via sentence-transformers; swappable via config. |
| D3 | Reports stored as structured JSON + rendered markdown, versioned per research run. |
| D4 | No separate `document_metadata` table; metadata on `documents`/`document_chunks` and denormalized into Qdrant payloads. |
| D5 | Trend engine computes deterministic transparent scores; LLM only interprets. |
| D6 | MVP retrieval = dense vectors + Qdrant payload filters (metadata, user scope); hybrid sparse retrieval is post-MVP. |
| D7 | Auth tokens: single JWT access token (no refresh in MVP); TTL configurable. |
| D8 | Agent selection per query type uses the deterministic routing table (§13.2); model per node via router (§11). |

## 25. Out of Scope for MVP (future extensions)

Custom LLM training, RL, Kubernetes, mobile app, complex knowledge graph, dozens of external APIs, autonomous web crawling, distributed microservices, billing/subscription, SaaS multi-tenancy, extra ML models, OCR, email verification, refresh tokens, sparse/BM25 hybrid retrieval.

## 26. Change Control

Architecture changes require: written rationale, impact on FR/NFR, affected DBML/graph sections, and approval. Append entries here with date, author, and description. The three spec artifacts must be updated together and stay consistent.

*(No changes yet — v1.0 frozen.)*
