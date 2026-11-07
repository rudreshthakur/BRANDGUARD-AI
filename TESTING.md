# Testing

All results below come from actual runs on **7 November 2026 (UTC)** against commit `HEAD` of this repository. Nothing is estimated.

## Summary of the latest run

| Check | Command | Result |
|---|---|---|
| Backend unit + API tests (SQLite) | `cd backend && python -m pytest -q` | **56 passed, 0 failed** |
| Backend tests on PostgreSQL 16 (clean venv from `requirements.txt`) | `DATABASE_URL=postgresql://… python -m pytest -q` | **56 passed, 0 failed** |
| AI provider contract tests (fake HTTP transport) | included in the 56 above | Anthropic and OpenAI-compatible request payloads, headers and URLs; response parsing; fallback on 401, 500, empty responses and timeouts; missing-key, missing-model and unknown-provider reporting |
| **Live AI model** | – | **Not tested.** No API key was available. |
| Frontend type check | `cd frontend && npm run typecheck` | **No errors** |
| Frontend unit tests (Vitest) | `npm test` | **6 passed** |
| Production frontend build | `npm run build` | **Succeeded** (JS bundle 282 kB, 84 kB gzip) |
| API health check | `GET /api/health` | `{"status":"ok","database":true}` |
| End-to-end judge journey (Playwright, fresh context with no storage) | `python e2e/test_judge_journey.py` | **16 of 16 steps passed**, no console errors |
| Labelled synthetic evaluation set | `cd backend && python -m eval.run_eval` | **26/26 expected issues found, 0 false positives, 8/8 compliant items clean, 8/8 approved claims verified** |
| Docker image build | `docker build .` | **Not run.** The authoring environment had no Docker daemon. The image steps were verified individually (see SETUP.md). |
| Public deployment check | – | **Not run.** The app is not yet deployed; see SUBMISSION.md. |

## Required judge test cases → automated tests

| # | Requirement | Test(s) |
|---|---|---|
| 1 | Prohibited term detection | `test_prohibited_preferred_and_brand_name_terms`, `test_role_permissions_on_knowledge` |
| 2 | Preferred terminology checks | `test_prohibited_preferred_and_brand_name_terms`, `test_docx_and_pdf_ingestion_preserve_metadata` |
| 3 | Supported claims not falsely flagged | `test_compliant_sample_has_no_invented_findings`, `test_number_words_and_compact_units` |
| 4 | Unsupported claims → "unable to verify" | `test_unsupported_claims_are_unable_to_verify`, `test_guarantee_language_needs_substantiation` |
| 5 | Conflicting approved facts detected | `test_conflicting_approved_facts`, `test_outdated_specification_detected_with_current_fact`, `test_superseding_a_fact_flags_old_value_as_outdated` |
| 6 | Compliant submission gets no invented violations | `test_compliant_sample_has_no_invented_findings`, `test_word_boundaries_avoid_false_positives`, `test_comparative_ignores_rather_than_and_other_than` |
| 7 | Invalid evidence IDs rejected | `test_invalid_evidence_ids_are_rejected`, `test_ai_output_is_validated_against_content_and_retrieved_evidence` |
| 8 | Citations point to real sources | `test_every_citation_points_to_a_real_source`, `test_rule_findings_cite_document_and_page` |
| 9 | Corrections preserve meaning | `test_suggestions_are_minimal_and_preserve_meaning`, `test_removal_suggestion_tidies_spacing` |
| 10 | Accepted correction → new version | `test_accept_creates_new_version_and_preserves_original`, `test_edit_applies_creator_text` |
| 11 | Rejected correction preserves original | `test_reject_preserves_original` |
| 12 | Reviewer can request changes | `test_full_review_loop` (+ E2E step 11) |
| 13 | Reviewer can approve revised content | `test_full_review_loop`, `test_approval_with_open_high_findings_requires_justification` |
| 14 | Review history accessible | `test_full_review_loop` (decisions + events), E2E "Audit history" |
| 15 | Malicious document instructions can't override prompts | `test_prompt_injection_in_content_is_flagged_and_inert`, `test_injection_flagged_in_uploaded_document_and_not_auto_approved`, `test_ai_output_is_validated_against_content_and_retrieved_evidence` |
| 16 | Missing API credentials don't crash | `test_missing_ai_credentials_do_not_crash_and_are_disclosed`, `test_health_and_status` |
| 17 | Backend failures give understandable errors | `test_backend_errors_are_understandable`, `test_malformed_ai_output_falls_back_gracefully` |
| 18 | Unsupported upload formats handled | `test_unsupported_upload_formats` |

Additional coverage: AI provider contracts (`tests/test_llm_providers.py`), workspace isolation, role permissions, DOCX/PDF metadata, guideline versioning and comparison, visual palette and contrast, brand drift from real data (including excluding samples), security headers, diff endpoint, re-approval after editing approved content.

## End-to-end journey (Playwright)

Run in a brand-new browser context, the equivalent of an incognito window:

1. Homepage opens without sign-in
2. Demo workspace launches with sample content
3. Compliant sample: zero findings, claims verified with citations
4. Unsupported 50% and superlative claims flagged as "Unable to verify"
5. Evidence opens with document, page, section and ID
6. Accepting a correction creates version 2 with the current spec
7. Version diff shows the original preserved
8. Creator re-audits and submits for review
9. Reviewer approves; decision and history recorded
10. Reviewer requests changes with a note
11. Uploaded document is pending, injection flagged, rules only proposed
12. Approving v2 of the guidelines supersedes v1; version comparison works
13. Brand Drift analytics render from stored data
14. Visual inspector flags off-palette colours and contrast
15. Audit history available
16. Responsive layout on a 390 px viewport

Screenshots from this run are saved in `e2e/artifacts/` (git-ignored) and used in the project PDF.

## Evaluation set: what the numbers mean

`backend/eval/eval_set.json` holds 20 synthetic items: 7 match the demo samples and 13 are additional. 8 should produce zero findings, and 26 expected issues are labelled with their expected evidence status. A finding counts as correct only if both the passage **and** the evidence status match.

**Caveat:** the same team wrote this set and the engine, and both target one synthetic brand. The perfect score shows the engine behaves as designed on these cases. It is a regression benchmark, **not** evidence of real-world accuracy. Independent, held-out test data from real brand teams is a Round 3 task.

## Adversarial probe (trying to break it)

After the benchmark passed, we wrote inputs the engine had not been tuned on. Findings:

| Input | Problem found | Status |
|---|---|---|
| "We are the #1 planner for teams." | **Marked as verified**: the "#1" support check matched the digit 1 inside unrelated facts | **Fixed**: superlative support now requires the same superlative phrase plus topical overlap. Regression test added. |
| "Pulse is guaranteed to save you time." | Not flagged | **Fixed**: guarantee language needs substantiation; suggests "designed to". |
| "Our battery lasts 10 hours longer than rivals." | Misread as an outdated spec | **Fixed**: relative claims are treated as comparisons. |
| "Beacon's battery lasts twelve hours." / "10h" | Spelled-out numbers and "h" not parsed | **Fixed** |
| "NORTHSTAR LABS is here." | Three overlapping findings | **Fixed**: low tone flags inside an existing rule violation are merged. |
| "Pulse cuts scheduling time by a third." | Fractions in words not detected | **Open**: listed in known limitations. |

## API break tests (final judge-style review)

| Attempt | Result |
|---|---|
| HTML/script and SQL text in title and content, emoji and Unicode | Stored and shown as plain text (React escapes output); queries are parameterised; audit ran normally |
| Accepting the same finding twice | Second attempt returns 409 "This finding is already accepted." |
| Unknown finding, version or submission IDs | 404 with clear messages |
| 11 MB upload | 413 "File exceeds the 10 MB limit." |
| 20,000-character submission | Audited in ~0.2 s |
| Pathological repetitive content (900 raw findings) | **Fixed:** findings are now capped at the 200 most severe, with a visible notice |
| Admin trigger `(a+)+$` (catastrophic-backtracking regex) | **Fixed:** triggers are now plain phrases separated by `|`, never raw regex. Regression test added. |
| Invalid workflow action, path traversal in API or static paths | 422 validation message; traversal returns only the app shell |
| Rule whose source guideline was superseded | Citation now says "(superseded version; rule still active)" |

## Bugs found by testing during the build

- The fetch hook treated the workspace-summary path `""` as "no request", leaving Overview, Settings and Voice blank on direct load. Found by E2E; fixed. A React error boundary was added.
- Uploading "Guidelines v4" created a separate document instead of a new version, because title-based lineage guessing was unreliable. Fixed with an explicit "New version of…" selector and a test.
- Brand Drift labels were ambiguous when truncated. Relabelled by metric.

## How to reproduce

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest -q && python -m eval.run_eval
cd ../frontend && npm ci && npm run typecheck && npm test && npm run build
cd ../backend && uvicorn app.main:app --port 8000 &      # serves the built frontend
pip install playwright && playwright install chromium
python ../e2e/test_judge_journey.py http://localhost:8000
```
