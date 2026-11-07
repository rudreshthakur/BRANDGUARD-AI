# BrandGuard AI

**Brand governance, before publishing.** An evidence-grounded brand compliance platform that catches inaccurate claims, off-brand messaging, terminology violations and basic visual inconsistencies before content goes live. Every finding cites the approved source behind it and comes with a small, editable fix. A human makes the final decision.

Team **Khiladi 786** · CodeNexus India 2026 · Round 2 build

**Live demo:** https://brandguard-ai-hndd.onrender.com (no login needed; free hosting, so allow about a minute for the first load) · **Source:** https://github.com/rudreshthakur/BRANDGUARD-AI

> Most AI marketing tools help create content. BrandGuard helps organisations decide whether that content is safe, accurate and consistent enough to publish, with traceable reasons and human control.

## Try it in 30 seconds

1. Open the [live app](https://brandguard-ai-hndd.onrender.com) and click **Launch demo workspace**. No sign-up is needed. You get a private copy of **Northstar Labs**, a fictional brand with synthetic guidelines, facts and sample content.
2. In **Content Auditor**, pick a sample (start with *Unsupported claims*) and click **Run brand audit**.
3. Click any citation to open the exact source passage. Accept, edit or reject a suggested fix; each accepted fix becomes a new version.
4. Click **Submit for review**, switch the role at the top to **Reviewer**, and approve or request changes.

## What it does

| Workflow step | Implementation |
|---|---|
| **Content input** | Paste copy and choose a channel (website, Instagram, ad, email, presentation, LinkedIn, press release). |
| **Approved knowledge check** | Content is checked only against *approved, current* knowledge in the same workspace: ingested PDF/DOCX/TXT guidelines (with page and section), approved facts with effective dates, and governance rules. |
| **Issue detection** | (1) Deterministic rule engine: prohibited, preferred and brand-name terms, forbidden claims, required phrases, numeric limits, channel rules, tone checks. (2) Claim verification: numeric claims are matched to approved facts by unit and context, then classified as *verified*, *conflict*, *outdated* or *unable to verify*; superlatives need substantiation. (3) Optional LLM contextual analysis with strict validation. (4) Prompt-injection detection. |
| **Explanations and evidence** | Each finding shows severity, evidence status, explanation, confidence, and validated citations (document, version, page, section, excerpt, evidence ID). Unknown or unretrieved evidence IDs are rejected. With no evidence, it says *"Unable to verify against approved knowledge."* |
| **Human decision** | Accept, edit or reject each fix (with immutable versions and a diff). Draft → Under review → Changes requested → Revised → Approved. Approving with open high or critical findings requires a written justification. Every action is logged. |

The three Round 1 differentiators are implemented as working features:
- **Evidence Traceability Engine:** evidence is always reloaded from the database by ID, never copied from model output. See `backend/app/services/evidence.py`.
- **Brand Drift Intelligence:** most-triggered rules, repeated terms, recurring unverified claims, a channel × category matrix, creator responses, and *guideline clarity signals* (rules whose suggestions creators keep rejecting). All are computed from stored data. See `backend/app/services/analytics.py`.
- **Intent-Preserving Corrections:** the smallest-span edit, shown as original | suggested | reason. Other findings' positions are re-anchored after each edit, and the original is never overwritten. See `backend/app/services/workflow.py`.

## Run locally

```bash
# backend (Python 3.11+)
cd backend && pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000          # API docs at http://localhost:8000/docs

# frontend (Node 20+), in a second terminal
cd frontend && npm install && npm run dev  # http://localhost:5173 (proxies /api to :8000)
```

Single-service mode (used for deployment): `cd frontend && npm run build`, then start uvicorn. The backend serves the built app at http://localhost:8000. See [SETUP.md](SETUP.md).

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): system design, data model, pipelines, security
- [SETUP.md](SETUP.md): local setup, environment variables, deployment (Render / Docker / Vercel)
- [TESTING.md](TESTING.md): test strategy and the latest recorded results
- [API.md](API.md): REST endpoints (interactive OpenAPI docs at `/docs`)
- [ROUND2_FEATURE_STATUS.md](ROUND2_FEATURE_STATUS.md): what is complete, partial or not built
- [ROUND3_ROADMAP.md](ROUND3_ROADMAP.md): the three committed Round 3 improvements
- [SUBMISSION.md](SUBMISSION.md): competition submission information, deadline status and checklist
- [RELEASE_AUDIT.md](RELEASE_AUDIT.md): documentation claims checked against the code; AI provider and repository audit

## Stack

React 18 + TypeScript + Tailwind CSS (Vite) · Python FastAPI · SQLAlchemy 2 on PostgreSQL (SQLite for local use) · PyMuPDF and python-docx for ingestion · Pillow for visual checks · optional LLM via a provider abstraction (Anthropic or any OpenAI-compatible API) · pytest, Vitest and Playwright.

## Honesty notes

- Northstar Labs and all demo data are **synthetic**. Demo submissions are labelled "synthetic sample" and can be excluded from analytics.
- The role switch (Creator / Reviewer / Admin) is a **demo mechanism**, enforced server-side. It is not production authentication.
- Retrieval in this build is BM25 lexical search, not embeddings or pgvector; the interface is ready for a swap. AI contextual analysis runs only when a provider key is configured, and the UI always states whether it ran. It has not been tested against a live model.
- No user research or accuracy metrics are claimed. Test results in TESTING.md are from actual runs.

## AI assistance disclosure

Significant parts of this codebase and documentation were produced with an AI coding assistant (Anthropic Claude) under the team's direction. See [SUBMISSION.md](SUBMISSION.md#ai-tools-and-external-services).

## Licence

MIT. See [LICENSE](LICENSE). Third-party libraries keep their own licences.
