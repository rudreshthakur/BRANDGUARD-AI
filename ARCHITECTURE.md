# Architecture

## Overview

```
 Browser (React + TS + Tailwind)
   Landing · Overview · Content Auditor · Submission proof desk · Review Queue
   Brand Knowledge · Visual Inspector · Brand Drift · Audit History · Settings
        │  JSON over HTTPS; headers X-Workspace-Token + X-Demo-Role
        ▼
 FastAPI application  (backend/app)
   routers/   public · workspace · knowledge · submissions
   deps.py    workspace isolation (hashed per-workspace token) + role enforcement
        │
        ▼
 Review orchestrator (services/auditor.py)
   1 security.py   prompt-injection scan (content treated as data)
   2 rules.py      deterministic rule engine (terms, names, forbidden claims,
                   required phrases, numeric limits, channel rules, tone)
   3 claims.py     claim extraction + verification against approved facts
   4 llm.py        optional contextual AI analysis (strict schema + validation)
   5 dedupe -> evidence.py final validation -> persist AuditRun + Findings
        │
        ▼
 Correction & review workflow (services/workflow.py) · Brand drift (services/analytics.py)
 Ingestion (services/ingestion.py) · Visual inspector (services/visual.py) · Audit log
        │
        ▼
 PostgreSQL (prod) / SQLite (local) via SQLAlchemy 2
```

In production the backend also serves the built frontend, so there is one URL and no CORS. Split hosting (Vercel + Render) is also supported through `VITE_API_BASE` and `BRANDGUARD_CORS_ORIGINS`.

## Data model (`backend/app/models.py`)

| Table | Purpose | Key constraints |
|---|---|---|
| `workspaces` | Organisation / brand workspace. Holds tone settings and palette. | Token stored only as SHA-256 hash |
| `sources` | A knowledge document *version*: lineage key, version, status, authority, effective date, injection flags | `UNIQUE(workspace, lineage_key, version)`; status ∈ pending_review / approved / superseded / rejected |
| `chunks` | Extracted, source-linked sections (page, section, text) | Cascade-deleted with source |
| `facts` | Approved facts and claims. Optional structured value/unit/metric, keywords, effective date, `superseded_by` | status ∈ approved / superseded / draft |
| `terms` | Governance rules: prohibited / preferred / brand_name / forbidden_claim / required_phrase / numeric_limit; optional channel scope and page/section | CHECK on kind, severity, status |
| `submissions` | Content item: channel, workflow status, current version, `is_sample` flag | CHECK on status |
| `content_versions` | **Immutable** text snapshots | `UNIQUE(submission, version_no)` |
| `audit_runs` | One audit of one version: AI mode/status, knowledge snapshot, verified claims, stats | |
| `findings` | Rule ID, category, severity, passage + span, explanation, evidence status, validated evidence JSON, confidence, suggestion, origin (rule / retrieval / ai / security), status | CHECK on severity |
| `corrections` | Accepted / edited / rejected decisions, with from/to versions | |
| `comments`, `review_decisions` | Collaboration and the decision trail, including open findings at decision time | |
| `audit_events` | Append-only activity log | |

Every query is scoped by `workspace_id`. Child objects are checked against the workspace before use.

## Knowledge ingestion pipeline

`Upload → Validate → Extract → Chunk → Attach metadata → Review → Approve → Index`

- **Validate:** extension allow-list (PDF/DOCX/TXT/MD), magic-byte checks (`%PDF`, ZIP with `word/document.xml`), size limit, binary detection for text files, rejection of password-protected PDFs.
- **Extract:** PyMuPDF (keeps page numbers) or python-docx (keeps heading styles). Headings are detected heuristically to attach `section`.
- **Chunk:** consecutive lines with the same page and section are merged into chunks of up to about 900 characters.
- **Review:** documents start as `pending_review` and are never used as evidence until approved. Text that resembles AI instructions is flagged to the admin. Rule patterns (`Use "X" instead of "Y"`, `Do not use "X"`, `Never claim "X"`, `Always write "X"`) become **proposed** rules that apply only if the admin ticks them.
- **Approve / version:** an upload can be marked as a new version of an existing document. Approval supersedes the previous version, which stays available for section-level comparison.

## Audit engine

**Deterministic rules (`rules.py`).** Phrase matching is case-insensitive and boundary-aware: hyphen-joined words don't match, so "cheap" won't match "cheapest" and "log in" won't match "login-page". Brand names flag any variant or wrong casing. Required phrases can be conditional (e.g. "free trial" requires "Terms apply.") and channel-scoped (Instagram needs `#NorthstarLabs`). Numeric limits apply to percentages in a trigger context.

**Claim verification (`claims.py`).**
1. Extract numeric claims (%, multipliers, durations, counts, currency) with normalised units.
2. Skip promotional offers ("40% off"); numeric limits govern those.
3. Find candidate facts that share the unit and at least one keyword within an 8-word window. The subject adds weight.
4. Compare against the best-matching metric: equal to a current fact → **approved** (listed as verified, with citation); equal to a superseded fact → **outdated** (shows current and superseded evidence); different → **verified conflict**. With no candidate, a substantiation-requiring claim is **unsupported** ("Unable to verify against approved knowledge — an evidence gap, not proof the claim is false").
5. Superlatives and comparatives are unsupported unless an approved fact substantiates them.

**Retrieval (`retrieval.py`).** BM25 over chunks from approved sources in the same workspace. It attaches the governing policy passage (e.g. Claims Policy, p. 3) to claim and tone findings. The `Retriever` interface is small so an embedding/pgvector retriever can replace it.

**AI analysis (`llm.py`).** A provider abstraction supports `anthropic`, `openai` (any compatible endpoint) and `mock` for tests. The system prompt treats `<content>` and `<evidence>` as data. Output must parse as strict JSON against a Pydantic schema. Each passage must be a verbatim substring of the content, or the finding is dropped. Evidence IDs must come from the set retrieved for that request *and* share vocabulary with the claim; otherwise they are dropped and the finding is marked "Unable to verify". Excerpts are reloaded from the database. Deterministic findings win any overlap. Failures and timeouts fall back to deterministic results, and the audit records why.

**Final validation (`auditor.finalise_evidence`).** Every evidence item is re-validated. Findings whose status requires evidence but has none are downgraded to *ambiguous*. Passages are re-anchored to the text.

## Corrections and versions

Accept, edit and reject act on one finding. Accept/edit locate the passage (preferring the stored span, otherwise the nearest occurrence), replace only that span, and tidy whitespace locally. This creates a new `content_versions` row and a `corrections` record. Remaining open findings in the same run are shifted, or marked `stale` if their text was touched. Reject keeps the text and records the reason, which feeds the clarity signals. Editing approved content returns it to draft.

## Review workflow

`draft → under_review → changes_requested → revised → approved`, with permissions enforced server-side:
- `submit` (creator/admin) requires an audit of the latest version.
- `request_changes` (reviewer) requires a note.
- `approve` (reviewer) requires the latest version to be audited. With open high or critical findings, it requires a justification of 10+ characters. The number of open findings is stored on the decision.
- Content under review is locked against edits.

## Security

- **Workspace isolation:** each workspace has a random 192-bit token, stored hashed and compared in constant time. Missing and forbidden workspaces return the same 404.
- **Roles:** the demo role header is validated and enforced on every mutating endpoint. Only admins change knowledge; only reviewers approve. This is labelled in the UI as a demo mechanism. *Production plan:* Supabase Auth JWT → membership table → the same role checks.
- **Input handling:** Pydantic validation with length limits, file type/size/magic checks, safe parser error messages, regex validation for admin triggers, and a generic 500 handler that never leaks internals.
- **Secrets:** the LLM key is server-side only (`BRANDGUARD_LLM_*`). `.env` is git-ignored and `.env.example` is provided.
- **Headers:** `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`. Demo creation is rate-limited per IP, and demo workspaces expire after 72 h.
- **Storage:** uploaded files are parsed in memory. Only extracted text is stored, so there are no public file URLs.

## Visual Inspector (basic, Round 2)

Pillow median-cut quantisation finds dominant colours. Each is matched to the nearest palette colour (CIE76 ΔE, tolerance 12). Off-palette colours covering ≥ 8% are flagged with palette evidence. The inspector checks whether the primary colour is present and computes the WCAG ratio between the two dominant colours. All visual findings are marked as needing human confirmation. An exact WCAG pair checker is included. There is no OCR, logo recognition or layout analysis yet; that is Round 3.
