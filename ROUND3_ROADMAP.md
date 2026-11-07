# Round 3 roadmap: three committed improvements

Each improvement builds on code that already exists in Round 2, so it does not need an architectural rewrite. Each also has a user-visible capability and measurable acceptance tests. None of these are claimed as complete in Round 2.

**Build order:** Improvement 2 → Improvement 3 → Improvement 1.

- *Versioning and impact analysis* builds directly on the fact/source versioning in Round 2 and adds the most governance value.
- *Multi-channel governance* builds on the channel field and channel-scoped rules.
- *The advanced Visual Inspector* has the most technical risk, so it goes last and is time-boxed. Its scope is reduced rather than delaying the other two.

---

## Improvement 1: Advanced Visual Brand Identity Inspector

**Existing capability (Round 2):** dominant-colour extraction, palette matching by ΔE with palette evidence, an exact WCAG pair checker, and a heuristic dominant-colour contrast flag. Every visual finding is marked for human confirmation.

**New functionality**
- Approved logo library: upload logo variants (primary, mono, reversed) with usage rules.
- Logo matching: detect approved logos in a creative by perceptual-hash and ORB feature matching over sliding windows. Report found, missing, wrong variant, distorted (aspect-ratio deviation) and clear-space violations.
- Colour deviation report per region: a grid-based palette map showing where off-palette colour sits.
- Text contrast on detected text regions: OCR (Tesseract) bounding boxes, then foreground/background sampling, then WCAG ratio per text block.
- Typography check where supported: compare OCR-detected font size ratios against the guideline hierarchy. Font identification is explicitly out of scope unless validated.
- Layout checks: safe-margin and logo-placement rules per channel format (e.g. Instagram 1080×1080 safe zone).
- Visual findings saved to a submission, with an image overlay of bounding boxes, using the same accept/reject and approval workflow.

**User problem solved:** brand managers can catch wrong logos, off-palette creatives and unreadable text before an ad ships, with the region marked.

**Technical implementation:** `services/visual.py` is extended with `logo_match.py` (OpenCV ORB + pHash), `ocr.py` (pytesseract) and region contrast. Images go in private object storage (Supabase Storage / S3) instead of memory only. An optional multimodal model offers *suggestions only*, never verdicts.

**Database changes:** `assets` (id, workspace, kind, file_ref, variant, usage_rule, version, status); `submission_assets` (submission ↔ uploaded creative); `visual_findings` (bbox JSON, region crop ref) or a `bbox` column on `findings`.

**API changes:** `POST/GET /knowledge/assets`; `POST /submissions` accepts an image; `GET /submissions/{id}/assets/{aid}/overlay`.

**UI changes:** Brand Knowledge gets an Assets tab. The submission page shows an image canvas with bounding boxes linked to finding cards.

**Test cases**
1. Creative containing the approved primary logo → "logo found", no violation.
2. Creative with a recoloured or mono logo where the primary is required → "wrong variant".
3. Logo stretched by 20% → distortion finding.
4. Teal text on Cloud background at small size → AA failure on that text block.
5. Photo-only creative → no false "missing logo" when the rule allows it.
6. Corrupt or oversized image → clear error.

**Completion criteria:** on a labelled set of at least 30 synthetic creatives, report measured logo-detection precision and recall (no target claimed in advance). Every finding has a bounding box and a palette/asset citation. Subjective checks always require human confirmation.

---

## Improvement 2: Guideline Versioning and Impact Analysis

**Existing capability (Round 2):** immutable document versions with explicit "new version of", approval that supersedes the previous version, section-level comparison, fact supersession with effective dates, and outdated-claim detection using superseded facts.

**New functionality**
- **Change impact report:** when a fact is superseded or a guideline version is approved, find previously approved or in-review content affected by the change.
- **Historical re-audit:** re-run audits for affected submissions against the new knowledge, in a background job. Show "was compliant → now outdated" deltas.
- **Rule-level diff:** compare rule sets between guideline versions (added, removed, changed severity or replacement), not just text.
- **Conflicting-fact detection:** flag two approved facts for the same subject and metric with different values and overlapping effective dates.
- **Effective dating:** facts and rules with future effective dates activate automatically. Audits record the knowledge snapshot (source versions and fact IDs) they used.
- **Source authority ranking:** when sources disagree, the higher-authority source wins (e.g. Legal over Marketing) and the conflict is shown.
- **Rule provenance:** rules whose source document was superseded are flagged for admin re-confirmation.

**User problem solved:** "We changed the battery spec, so which live pages are now wrong?" Today that takes a manual search; BrandGuard lists them with evidence.

**Technical implementation:** a `services/impact.py` that indexes `findings`/`verified_claims` by fact ID and metric, plus a fast pre-filter on submission text (unit + keyword match) before re-audit. A job queue (RQ/Celery, or FastAPI background tasks for the hackathon). The knowledge snapshot already stored in `audit_runs` is extended to fact and term IDs.

**Database changes:** `impact_reports` (id, trigger type, trigger id, created_at, summary); `impact_items` (report, submission, previous status, new status, finding ids); `facts.authority_rank`; `terms.source_version_confirmed`; index on `findings(rule_id)`.

**API changes:** `GET /knowledge/impact?fact_id=|source_id=`; `POST /knowledge/impact/{id}/reaudit`; `GET /knowledge/conflicts`; `GET /knowledge/sources/{id}/rule-diff/{other}`.

**UI changes:** after approving a change, an "Impact" panel shows affected content with a re-audit button. A conflicts banner appears in Brand Knowledge. A per-submission badge says "affected by guideline change".

**Test cases**
1. Supersede battery 12 h → 14 h: the previously approved "12 hours" page appears in the impact report and becomes outdated on re-audit.
2. Content that doesn't mention battery life is not listed (no false impact).
3. Two approved facts with different values for the same metric → conflict reported.
4. A future-dated fact doesn't apply until its date.
5. Guideline v2 removes a prohibited term → rule diff shows "removed", and old findings for it are marked "rule retired".

**Completion criteria:** impact report lists every affected submission in the test fixture (verified against a hand-labelled list), re-audit results stored as new runs, and no affected item missed in the fixture.

---

## Improvement 3: Multi-Channel Brand Governance

**Existing capability (Round 2):** a channel on every submission, channel-scoped rules (e.g. Instagram hashtag), channel in analytics, and a channel × category matrix.

**New functionality**
- **Channel policy packs:** per-channel configuration covering length limits (e.g. Instagram 2,200 characters, LinkedIn post length, ad headline limits), required elements (hashtag, disclosure, CTA), banned elements, emoji and hashtag limits, and link rules.
- **Presentations and documents as content:** upload PPTX/DOCX/PDF content. Each slide or page becomes a separately audited unit with page-level findings.
- **Review assignments:** route by channel and risk. Regulated claims go to a Legal reviewer; others go to the Brand manager.
- **Approver escalation:** critical findings or overrides need a second approver. Optional SLA reminders.
- **Team collaboration:** finding-level comment threads, @mentions, and a reviewer workload view.
- **Cross-channel analytics:** drift per channel over time, and the same claim appearing in different forms across channels.

**User problem solved:** one campaign ships to Instagram, the website and a sales deck with different rules and owners. Teams need one place that applies the right rules per channel and routes to the right approver.

**Technical implementation:** a `channel_policies` table read by a new `rules.channel_checks()` step; python-pptx for slide extraction; assignment rules evaluated on submit; `review_assignments`; a second approval step in `workflow.TRANSITIONS`. Introduce real accounts (Supabase Auth → `memberships` with role) so assignments refer to people.

**Database changes:** `channel_policies` (workspace, channel, max_length, required JSON, banned JSON, hashtag_limit); `users`, `memberships`; `review_assignments` (submission, user/role, stage, due_at, status); `content_units` (submission, page/slide no, text).

**API changes:** `GET/PUT /channels/{channel}/policy`; `POST /submissions` accepts PPTX/DOCX/PDF; `GET /me/assignments`; `POST /submissions/{id}/escalate`.

**UI changes:** a Channel policies editor in Brand Knowledge, a slide-by-slide audit view, a "My reviews" queue, an escalation indicator, and channel filters on Brand Drift.

**Test cases**
1. An Instagram caption over the limit → length finding; the same text on the website → none.
2. A paid-ad channel missing the "Ad" disclosure → finding.
3. A deck with three slides, one slide conflicting → finding on slide 2 only.
4. A critical finding → approval requires a second approver.
5. Assignments route a health-claim submission to the Legal reviewer.

**Completion criteria:** at least 4 channel packs configurable in the UI, slide-level audits on PPTX, two-stage approval enforced server-side, and cross-channel drift computed from stored data.

---

## Dependencies

- Improvement 3's assignments need real user accounts. Do these early in Round 3, as they also replace the demo role switch for authenticated use while keeping the public demo mode.
- Improvement 1 needs private object storage for images, which can also be shared with Improvement 3's document uploads.
- Improvement 2's re-audit job queue is reused by Improvement 3's bulk audits.
