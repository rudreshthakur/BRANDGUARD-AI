# Release audit (pre-submission)

An independent check of what the documentation claims against what the code does. It was carried out after an external review of the Round 2 package.

## Differentiator claims vs code

| Claim | Where it lives in the code | Verified by | Verdict |
|---|---|---|---|
| Evidence is reloaded from the database by ID; model text is never shown as evidence | `services/evidence.py` (`EvidenceValidator.materialise/validate`), `services/auditor.py` (`finalise_evidence`) | `test_every_citation_points_to_a_real_source`, `test_invalid_evidence_ids_are_rejected` | ✅ True |
| Unknown, unapproved or unretrieved evidence IDs are rejected | `EvidenceValidator.validate` (`allowed_ids`, status filter, vocabulary overlap) | `test_ai_output_is_validated_against_content_and_retrieved_evidence` | ✅ True |
| Unsupported claims say "Unable to verify against approved knowledge" and are distinguished from false claims | `services/claims.py` (`unsupported`/`ambiguous` vs `verified_conflict`/`outdated`) | `test_unsupported_claims_are_unable_to_verify`, `test_conflicting_approved_facts` | ✅ True |
| "Every finding cites a source" | Rule, fact, claim and tone findings carry evidence. **Security notices carry none by design**, and AI findings may have none (then labelled "Unable to verify"). | Manual review | ⚠️ Overstated in one place (landing page). **Reworded.** Other documents already say "where available". |
| Brand Drift is computed only from stored records | `services/analytics.py` reads `findings`, `corrections`, `review_decisions` | `test_brand_drift_uses_real_data_and_can_exclude_samples` | ✅ True |
| Synthetic samples are labelled and can be excluded | `Submission.is_sample`, `include_samples` flag, UI banner and toggle | same test | ✅ True |
| Corrections replace only the flagged span and never overwrite the original | `services/workflow.py` (`apply_correction`, immutable `content_versions`) | `test_accept_creates_new_version_and_preserves_original`, `test_reject_preserves_original` | ✅ True |
| Suggestions are "minimal" | Deterministic suggestions only touch the flagged span. AI suggestions are not forced to be minimal; they are labelled "AI-suggested … review before accepting". | `test_suggestions_are_minimal_and_preserve_meaning` (deterministic only) | ✅ True for deterministic. AI caveat documented. |

## AI provider integration

| Item | Finding | Action |
|---|---|---|
| Anthropic request | `POST /v1/messages`, headers `x-api-key` and `anthropic-version: 2023-06-01`, `system` + `messages`, `temperature 0`, `max_tokens 1500`. Default model `claude-haiku-5-5`, overridable with `BRANDGUARD_LLM_MODEL`. | Contract test added |
| OpenAI-compatible request | `POST {base}/chat/completions`, Bearer auth, `response_format: json_object` (the prompt contains "JSON", as that mode requires) | Contract test added |
| OpenAI default model | Was a hard-coded guess (`gpt-4o-mini`) that can't be verified for late 2026 | **Fixed:** the model is now required and the status explains it if missing |
| Missing or invalid configuration | Previously reported only "not configured" | **Fixed:** specific messages for missing key, missing model and unknown provider |
| Error handling | `IndexError`/`TypeError` from unexpected response shapes weren't caught | **Fixed:** all fall back to deterministic results with the reason recorded. The key is never echoed. |
| Structured output | Pydantic schema, verbatim passages, retrieved-ID check, overlap check | Already tested |
| **Live model run** | **Not performed.** No API key was available. | Documented everywhere as untested |

## Repository readiness

| Check | Result |
|---|---|
| Secrets / API keys | None found (`git grep` for key patterns; `.env` ignored; `.env.example` holds placeholders only) |
| Commit history | Genuine commits from 7 Nov 2026 (IST evening), plus GitHub's initial commit and a merge on 8 Nov when pushing to https://github.com/rudreshthakur/BRANDGUARD-AI. **Not rewritten or backdated.** |
| Personal data | Member names appear in LICENSE, README and the report, as in the Round 1 proposal. **Commits are authored as "Team Khiladi 786" with a personal Gmail address**, which becomes public when pushed. The team should decide whether that is acceptable. We have **not** rewritten history to change it. Future commits can use a different address. |
| Large or generated files | `node_modules`, `dist`, databases and test artifacts are git-ignored |
| Licences | MIT for project code. PyMuPDF is AGPL-3.0 (noted in LICENSE). Fonts are SIL OFL. |

## Deployment readiness

| Check | Result |
|---|---|
| `render.yaml` | Parses; defines web service `brandguard-ai` (Docker, `/api/health`) and database `brandguard-db` |
| Production path | Built frontend served by FastAPI; full test suite passes on PostgreSQL 16 from a clean venv |
| Docker image | Not built by us locally (no Docker daemon). **Render built it successfully** from the same Dockerfile during deployment (reported by the team). |
| Live deployment | **Live:** https://brandguard-ai-hndd.onrender.com (Render web service + Render PostgreSQL 18), deployed by the team on 8 Nov 2026. See the update below for what has and hasn't been verified. |

## Deadline

See SUBMISSION.md. The original deadline was 7 Nov 2026, 10:00 AM IST, and all commits are later that day. **No evidence of an extension has been supplied**, so none is claimed.


---

## Update: 8 November 2026 (after deployment)

### What changed since the previous audit

| Previous status | Current status | How verified |
|---|---|---|
| Not deployed; no URL | Live at https://brandguard-ai-hndd.onrender.com (Render, blueprint `brandguard-ai`, PostgreSQL 18) | Reported by the team. Our sandbox can't reach onrender.com, so **we could not open the live site ourselves.** |
| Not on GitHub | Public at https://github.com/rudreshthakur/BRANDGUARD-AI, branch `main` | **Verified:** cloned it; its content is identical to our last release (`597d4f0`), plus GitHub's initial commit and a merge |
| Test counts in docs | 58/58 backend tests (2 new tests added in this update) on SQLite and on local PostgreSQL 16 | Re-run on this update |

### Production issues found in the Render configuration

| Issue | Impact | Action |
|---|---|---|
| uvicorn only trusted forwarded headers from 127.0.0.1, so behind Render's proxy **every visitor appeared to come from the same IP** | The "30 demo workspaces per IP per hour" limit applied to **all judges combined** and could block demo launches during judging | **Fixed** in the Dockerfile (`--forwarded-allow-ips='*'`, safe because Render's proxy is the only ingress). Test added. Takes effect after the next Render deploy. |
| No way to confirm from outside which database the live app uses | Couldn't verify the PostgreSQL connection | **Added** `database_backend` to `/api/health` (it reports `postgresql` or `sqlite`; never connection details). Takes effect after the next deploy. |
| Free Render Postgres **expires 30 days after creation** (Render docs) | The demo stops working around **7–8 Dec 2026**; data is deleted 14 days later | Documented. Upgrade the database before then if needed. |
| Free web service sleeps after 15 min idle (about 1 min to wake) | A judge's first visit can look broken | Documented. Open the URL shortly before judging. |
| Expired-workspace cleanup relied on database cascades and had no test | Possible orphaned data on PostgreSQL | **Test added**; passes on SQLite and PostgreSQL. |
| PostgreSQL version | Render runs 18; our tests ran on 16 | Low risk (standard SQL via SQLAlchemy). Noted. The team's live tests indicate the app works on 18. |

### Is the live app on PostgreSQL?

Very likely, but **not verified**. `render.yaml` wires `DATABASE_URL` from `brandguard-db`. If that variable were missing, the app would fall back to SQLite (the Dockerfile default), lose data on every restart, and still look healthy. Confirm with `https://brandguard-ai-hndd.onrender.com/api/health` after deploying this update: it should show `"database_backend": "postgresql"`.

### Live workflow coverage

| Flow | Live site | Automated (local) |
|---|---|---|
| Open without login | ✅ reported by team | ✅ E2E |
| Audit violating content → findings with evidence | ✅ reported by team (5 findings) | ✅ |
| Audit clean content → no findings | ✅ reported by team | ✅ |
| Open evidence drawer | ⬜ not checked | ✅ |
| Accept / edit / reject fix → new version | ⬜ not checked | ✅ |
| Submit → Reviewer requests changes / approves | ⬜ not checked | ✅ |
| Admin uploads and approves a guideline version | ⬜ not checked | ✅ |
| Brand Drift, Visual Inspector, Audit History | ⬜ not checked | ✅ |
| AI contextual analysis | ⬜ not configured (no API key); shows "unavailable" | contract tests only |

### Round 3 and contributions

- Round 3 improvements are labelled as **proposed, not built** in ROUND3_ROADMAP.md, SUBMISSION.md and the report.
- Individual contributions remain **TODO**. Nothing has been attributed to any member.

### Deadline

Unchanged: the original deadline was 7 Nov 2026, 10:00 AM IST. Development, the GitHub push and the deployment all happened after it. **No official extension has been supplied, so none is claimed and eligibility is unconfirmed.**
