# Round 2 submission: BrandGuard AI

> **Fill in before submitting:** the items marked `TODO` need the team's own accounts or information. Nothing here has been submitted on the team's behalf.

## ⚠️ Status and rule notes (read first)

1. **Deadline and eligibility: UNVERIFIED.** The Round 2 email states **7 November 2026, 10:00 AM IST**. An independent reviewer reports that the official event page says there is **no late window** and that missing the deadline ends participation. (We could not open the official page from our build environment to confirm this.) The team said the deadline was extended, but **no official announcement or written confirmation has been supplied**, so this document does **not** claim an extension.
   - The project's commits were made on **7 November 2026 from 10:47 PM IST onwards** (17:17 UTC onwards). The GitHub repository was created and the code pushed around **12:00–12:25 AM IST on 8 November**, and the Render deployment followed. All of this is **after** the original deadline. These timestamps are authentic and must not be changed.
   - *TODO (team): if the organisers granted an extension, save the email or announcement and add it here. If not, contact the organisers before submitting and follow their answer. Do not describe this as an on-time Round 2 submission without that confirmation.*
2. **Who submits: conflicting instructions.** The Round 2 email says **only the team leader submits one team entry**. The current event page (wecodecoders.in/events/codenexus-india) says **each member submits individually, declaring their own role and contribution**. We have prepared both versions below. **Follow whatever the live submission portal asks for.** If it is still unclear, email the organisers and keep their reply.
3. **Round 3 eligibility** is not assumed. Check the portal or email for selection results.

## 1. Project name
BrandGuard AI: Brand Governance, Before Publishing.

## 2. Team name
Khiladi 786

## 3. Team details

| Member | Planned role (from the Round 1 proposal) |
|---|---|
| Sarthak Agrawal (Team Lead) | Integration, scope, architecture, task tracking, final demo |
| Rudresh Kumar | Frontend / UI |
| Arpit Singh | AI / RAG / evaluation |
| Pranjal Gautam | Backend / database |

*TODO: confirm emails and contact details from the portal, and correct the roles above to what each person actually did (see §16).*

## 4. Working application link
**https://brandguard-ai-hndd.onrender.com**. Deployed on Render from `render.yaml`: web service `brandguard-ai` (Docker) and database `brandguard-db` (Render PostgreSQL 18). No login is required.

- **Checked by the team (manual, 8 Nov 2026):** the site opens without login. A violating text produced 5 findings (4 high, 1 low) with guideline references, evidence, explanations and suggested fixes. A clean text produced 0 open findings.
- **Not yet checked on the live site:** the full Creator → Reviewer → Admin workflow (accept a fix, submit, request changes or approve, admin document upload), the evidence drawer, the Brand Drift and Visual Inspector pages, and which database the live service is using. The same flows pass automated tests locally (see TESTING.md), but that is not proof they work in production. Run the live checklist at the end of this file.
- **Free-tier limits:** the service sleeps after 15 minutes idle and takes about a minute to wake, so open it shortly before judging. The free database **expires 30 days after creation (around 7–8 December 2026)**; upgrade it before then if the demo must stay up.

## 5. Public repository link
**https://github.com/rudreshthakur/BRANDGUARD-AI** (public, branch `main`). History is genuine and has not been rewritten. Commits are authored as "Team Khiladi 786" (with a member's personal email) plus GitHub's initial commit by `rudreshthakur`.

## 6. Updated project PDF
`docs/BrandGuard_AI_Round2_Project_Report.pdf` in this repository. Upload it, or link it from the repo.

## 7. Completed features
See [ROUND2_FEATURE_STATUS.md](ROUND2_FEATURE_STATUS.md) for the full table. Highlights:
- A complete judge workflow with no login: **content input → approved-knowledge check → issue detection → explanations and evidence → human decision**.
- Brand Knowledge Hub: PDF/DOCX/TXT/MD ingestion with page and section metadata, review/approval, proposed rules, fact and guideline versioning with comparison, terminology and claim rules, channel-scoped rules.
- Audit engine: deterministic rules, claim verification (verified / conflict / outdated / unsupported), superlative/guarantee/comparative checks, prompt-injection detection, optional validated LLM analysis.
- Evidence Traceability Engine: validated citations with document, version, page, section, excerpt and ID. Explicit "Unable to verify against approved knowledge".
- Intent-preserving corrections: accept/edit/reject, immutable versions, diff, re-anchoring.
- Review workflow: Draft → Under review → Changes requested → Revised → Approved, comments, justification for high-severity overrides, audit log.
- Brand Drift Intelligence from stored data, including guideline clarity signals.
- Basic Visual Inspector: palette compliance and WCAG contrast.
- One-click private demo workspace with the synthetic Northstar Labs brand and 7 samples, including a compliant one.

## 8. Technology stack
React 18, TypeScript, Tailwind CSS, Vite · Python 3, FastAPI, Pydantic 2, SQLAlchemy 2 · PostgreSQL (SQLite locally) · PyMuPDF, python-docx · Pillow · httpx-based LLM provider abstraction (Anthropic / OpenAI-compatible, optional) · pytest, Vitest, Playwright · Docker and a Render blueprint.

## 9. Technical implementation details
See [ARCHITECTURE.md](ARCHITECTURE.md). In brief:
- The audit orchestrator runs a security scan, the rule engine, claim verification against approved facts (unit + keyword-window matching, value comparison, superseded-fact detection), BM25 retrieval of governing policy passages, and optional AI analysis. It then deduplicates, re-validates every evidence item against the database, and stores the audit run with findings.
- The LLM can't create citations. Output must match a strict schema, passages must be verbatim, and evidence IDs must come from the retrieved set. Excerpts are always reloaded from the database.
- Content versions are immutable, and every correction or edit creates a new version.

## 10. Comparison with the Round 1 plan
The product follows the proposal's workflow, six modules and three differentiators. See "Changes from the Round 1 plan" in ROUND2_FEATURE_STATUS.md.

## 11. Scope reductions and architectural changes
- Supabase Auth was replaced by a per-workspace token and a labelled demo role switch, so judges need no login.
- pgvector embeddings were replaced by BM25 lexical retrieval behind a swappable interface.
- The LLM is optional; deterministic and retrieval checks are the backbone.
- Uploaded files are parsed in memory with no object storage.
- Not built: logo matching, document/image content submissions, assignment/escalation, real accounts.

## 12. Three major Round 3 improvements (proposed, not built)
These are **commitments for Round 3. None of them is implemented in the Round 2 build**, beyond the foundations named in ROUND3_ROADMAP.md. Details are in [ROUND3_ROADMAP.md](ROUND3_ROADMAP.md).
1. **Advanced Visual Brand Identity Inspector:** logo matching and variant detection, region colour maps, OCR-based text contrast, layout and safe-zone checks, visual evidence overlays.
2. **Guideline Versioning and Impact Analysis:** change impact reports, historical re-audit, rule-level diffs, conflicting-fact detection, effective dating, source authority.
3. **Multi-Channel Brand Governance:** channel policy packs, slide/page-level audits for decks and documents, review assignment and escalation, team collaboration, cross-channel drift analytics.

## 13. Actual testing outcomes
See [TESTING.md](TESTING.md). Latest run (7 Nov 2026):
- 58/58 backend tests on SQLite and on PostgreSQL 16 (local), including 10 AI provider contract tests using a fake HTTP transport
- 6/6 frontend unit tests, clean type check, successful production build
- 16/16 end-to-end browser steps
- Team-authored synthetic evaluation set: 26/26 expected issues, 0 false positives (a regression benchmark, not independent accuracy)
- An adversarial probe found 6 weaknesses, and 5 were fixed.

## 14. Limitations
- Demo role switch, not real authentication.
- Lexical retrieval, so paraphrased claims can be missed if no keyword overlaps an approved fact. Fractions in words ("by a third") are not parsed.
- AI contextual analysis has not been tested against a live model (no API key was available); its validation logic is tested with a mock provider.
- The Visual Inspector analyses colour only. Its contrast flag is heuristic and needs human confirmation.
- Free hosting tiers sleep when idle, so the first request may be slow.
- The evaluation data is synthetic and team-authored. No user research has been conducted yet. The Round 1 research plan still stands, and no findings are claimed.

## 15. AI tools and external services
- **AI coding assistant:** Anthropic Claude (Claude Opus 5.5, via Claude) generated a substantial share of the code, tests and documentation in this repository, under the team's direction. *TODO: list any other AI tools the team used (e.g. ChatGPT, Copilot) and for what.*
- **Runtime AI (optional, off by default):** Anthropic Messages API or any OpenAI-compatible Chat Completions API, selected with `BRANDGUARD_LLM_PROVIDER`. Only the submitted text and retrieved approved evidence are sent. Disabled in the default deployment. **It has not been tested against a live model**: request and response handling is verified with a fake HTTP transport only.
- **Open-source libraries:** React, React Router, Tailwind CSS, Vite, lucide-react, @fontsource (IBM Plex Sans, Source Serif 4: SIL OFL), FastAPI, Pydantic, SQLAlchemy, Uvicorn, PyMuPDF (AGPL-3.0; note the licence terms if you distribute), python-docx, Pillow, httpx, psycopg, pytest, Vitest, Playwright.
- **Pre-existing code or templates:** none. The project was built from scratch in this repository. Northstar Labs is a fictional brand created for this project.

## 16. Team responsibilities and actual contributions
*TODO: each member writes their **actual** contribution here. Do not copy the planned roles if they differ. Judges may ask for evidence.* Suggested format:

| Member | What I actually did | Evidence (commits, files, docs, demo prep) |
|---|---|---|
| Sarthak Agrawal | TODO | TODO |
| Rudresh Kumar | TODO | TODO |
| Arpit Singh | TODO | TODO |
| Pranjal Gautam | TODO | TODO |

### If the portal asks for individual submissions (per-member template)
```
Name:
Team: Khiladi 786   Project: BrandGuard AI
Role:
My contribution (specific features/files/tasks):
AI tools I used and how:
Working link:            Repository:            PDF:
```

## Pre-submission checklist

- [ ] Deadline/extension status confirmed in writing by the organisers (or eligibility clarified); proof saved
- [ ] Submission mode confirmed (team leader only vs every member)
- [x] Repository pushed to a public GitHub repo (https://github.com/rudreshthakur/BRANDGUARD-AI) *(reported by the team)*
- [x] App deployed on Render (https://brandguard-ai-hndd.onrender.com); opens without login *(reported by the team)*
- [ ] Open `https://brandguard-ai-hndd.onrender.com/api/health` and confirm `"database_backend": "postgresql"` (available after this update is deployed)
- [ ] Live: **Launch demo workspace** → *Unsupported claims* sample → Run brand audit → open a citation (evidence drawer)
- [ ] Live: *Outdated specification* sample → **Accept** the fix → version 2 appears → **Re-run brand audit** → **Submit for review**
- [ ] Live: switch role to **Reviewer** → add a note → **Approve**; on another item, **Request changes** with a note
- [ ] Live: switch role to **Admin** → Brand Knowledge → upload the sample `Northstar_Brand_Guidelines_v4_draft.txt` as a new version → it shows a warning and stays pending → approve it
- [ ] Live: Brand Drift and Visual Inspector pages load; Audit History shows the actions above
- [ ] Repeat the first live check in a private/incognito window
- [ ] PDF link opens without sign-in
- [ ] Remaining TODOs in this file completed (individual contributions, other AI tools, deadline evidence)
- [ ] No secrets in the repo (`git grep -i "api_key\|secret"` shows only placeholders)
- [ ] Service warmed up shortly before judging (free tier cold starts)
