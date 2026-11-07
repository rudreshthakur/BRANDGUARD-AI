# Round 2 feature status

Legend: ✅ complete and tested · 🟡 partial (scope stated) · ⬜ not built in Round 2

## Central workflow (scored in Round 2)

| Step | Status | Notes |
|---|---|---|
| Content input | ✅ | Paste text, choose title and channel. Seven channels. Length validation. |
| Approved brand knowledge check | ✅ | Only approved, current, same-workspace knowledge is used. Superseded facts are used only to detect outdated claims. |
| Issue detection | ✅ | Deterministic rules, claim verification, prompt-injection scan, and optional AI analysis. |
| Explanations and evidence | ✅ | Validated citations (document, version, page, section, excerpt, ID). Explicit "Unable to verify" for gaps. |
| Human decision | ✅ | Accept/edit/reject, immutable versions, submit → request changes / approve, justification for high-severity overrides. |

## Module 1: Brand Knowledge Hub

| Feature | Status | Notes |
|---|---|---|
| Guideline upload (PDF, DOCX, TXT, MD) | ✅ | Type, magic-byte and size validation; page and section metadata. |
| Inspect extracted text | ✅ | Chunk viewer with page, section and ID. |
| Review → approve / reject | ✅ | Pending documents are never used as evidence. |
| Rule extraction from documents | 🟡 | Pattern-based proposals ("Use X instead of Y", "Do not use X", "Never claim X", "Always write X") that need admin approval. No AI extraction. |
| Approved facts (manual) | ✅ | Structured value/unit/keywords and effective dates. |
| Fact versioning (supersede) | ✅ | Old values are then flagged as outdated. |
| Preferred / prohibited terms, brand names, forbidden claims, required phrases, numeric limits | ✅ | Channel scoping supported. |
| Tone guidelines | 🟡 | Deterministic checks (exclamations, all caps, sentence length) plus a voice description. Deeper tone analysis needs an AI provider. |
| Guideline version management | ✅ | Explicit "new version of", approval supersedes, section comparison. |
| Brand assets (logo files) | ⬜ | Palette only. Logo library is Round 3. |

## Module 2: Content Auditor

| Feature | Status | Notes |
|---|---|---|
| Exact terminology checks | ✅ | Boundary-aware, case-insensitive; brand-name casing. |
| Fact verification / claim checking | ✅ | Numeric claims (digits, number words, %, x, durations, counts, currency): verified / conflict / outdated / unsupported. Superlatives, guarantees and comparatives need substantiation. |
| Brand tone analysis | 🟡 | Deterministic rules always; contextual AI tone only with a configured provider. |
| Contextual messaging checks | 🟡 | Via the AI provider, with strict validation. Not exercised against a live model in our testing (no key available); validated with a mock provider. |
| Document upload as content (not just text) | ⬜ | Content is pasted text in Round 2. |

## Module 3: Visual Inspector (basic)

| Feature | Status | Notes |
|---|---|---|
| Brand-colour checks | ✅ | Dominant colours vs palette (ΔE), with palette evidence. |
| Contrast checks | ✅ | Exact WCAG pair checker, plus a heuristic dominant-colour contrast flag. |
| Logo checks | ⬜ | Round 3 (Improvement 1). |
| Typography / layout | ⬜ | Round 3. |

## Module 4: Correction Engine

| Feature | Status |
|---|---|
| Sentence/phrase-level minimal suggestions | ✅ |
| Original / suggested / reason view | ✅ |
| Accept, edit, reject | ✅ |
| Original preserved; every change is a new version; diff view | ✅ |
| Other findings re-anchored after an edit | ✅ |

## Module 5: Review Workflow

| Feature | Status | Notes |
|---|---|---|
| Creator / Reviewer / Admin roles | 🟡 | Enforced server-side via a demo role switch. No real user accounts. |
| Draft → Under review → Changes requested → Revised → Approved | ✅ | |
| Comments, decision notes, decision trail | ✅ | |
| Audit history | ✅ | Append-only events, filterable. |
| Separate manager vs approver tiers, assignment, escalation | ⬜ | Round 3 (Improvement 3). |

## Module 6: Insights (Brand Drift Intelligence)

| Feature | Status |
|---|---|
| Totals, severity, category, evidence outcome | ✅ |
| Most-triggered rules with submission and channel spread | ✅ |
| Repeated terminology / tone violations | ✅ |
| Recurring unverified claims | ✅ |
| Channel × category matrix | ✅ |
| Creator responses (accepted / edited / rejected) | ✅ |
| Guideline clarity signals (high rejection rate) and training signals (rule recurring across submissions) | ✅ |
| Toggle to exclude synthetic sample data | ✅ |

## Platform

| Feature | Status | Notes |
|---|---|---|
| One-click demo workspace, no registration | ✅ | Private sandbox per visitor; expires in 72 h. |
| Northstar Labs synthetic brand, 7 samples incl. compliant | ✅ | |
| Workspace data isolation | ✅ | Hashed token per workspace. |
| PostgreSQL support | ✅ | Full test suite passes on PostgreSQL 16. |
| pgvector / semantic retrieval | ⬜ | BM25 lexical retrieval behind a swappable interface. |
| Supabase Auth / real accounts | ⬜ | Documented production plan. |
| Public deployment | ⬜ | Render blueprint and Dockerfile ready; needs the team's Render account (see SUBMISSION.md). |

## Changes from the Round 1 plan

- **Authentication:** the plan proposed Supabase Auth. The build uses per-workspace tokens and a labelled demo role switch, because the Round 2 rules require judges to use the product without a login. Real accounts are deferred.
- **Retrieval:** the plan proposed pgvector embeddings. The build uses BM25 so the demo is deterministic and needs no embeddings API key. The retriever interface allows a later swap.
- **AI role:** the plan used LLM analysis as a core step. The build makes deterministic and retrieval checks the backbone; the LLM is optional and strictly validated. This makes the core flow reliable without credentials and keeps the model from being the source of truth, as the plan intended.
- **Storage:** uploads are parsed in memory and only extracted text is stored, rather than keeping files in object storage.
- **Deployment:** a single service (API serves the built UI) instead of a Vercel + Render split, to reduce moving parts. The split is still supported.
