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
| Commit history | 6+ genuine commits on 7 Nov 2026 (IST evening). **Not rewritten or backdated.** |
| Personal data | Member names appear in LICENSE, README and the report, as in the Round 1 proposal. **Commits are authored as "Team Khiladi 786" with a personal Gmail address**, which becomes public when pushed. The team should decide whether that is acceptable. We have **not** rewritten history to change it. Future commits can use a different address. |
| Large or generated files | `node_modules`, `dist`, databases and test artifacts are git-ignored |
| Licences | MIT for project code. PyMuPDF is AGPL-3.0 (noted in LICENSE). Fonts are SIL OFL. |

## Deployment readiness

| Check | Result |
|---|---|
| `render.yaml` | Parses; defines web service `brandguard-ai` (Docker, `/api/health`) and database `brandguard-db` |
| Production path | Built frontend served by FastAPI; full test suite passes on PostgreSQL 16 from a clean venv |
| Docker image | **Not built** (no Docker daemon in the build environment) |
| Live deployment | **Not done.** No hosting credentials. No URL exists. |

## Deadline

See SUBMISSION.md. The original deadline was 7 Nov 2026, 10:00 AM IST, and all commits are later that day. **No evidence of an extension has been supplied**, so none is claimed.
