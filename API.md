# API reference

Interactive OpenAPI documentation is served at **`/docs`** (Swagger UI) and `/openapi.json`.

Workspace endpoints live under `/api/w/{workspace_id}` and require:
- `X-Workspace-Token`: returned when the workspace is created (stored hashed server-side)
- `X-Demo-Role`: `creator` | `reviewer` | `admin` (demo role switch; enforced per endpoint)

Errors always return `{"detail": "<human-readable message>"}` with an appropriate status code (400, 403, 404, 409, 413, 415, 422, 429, 500).

## Public

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness and database check |
| GET | `/api/system/status` | Version, AI provider status, retrieval mode, limits |
| GET | `/api/samples` | Synthetic sample content (Northstar Labs) |
| GET | `/api/samples/files` · `/api/samples/files/{name}` | Synthetic documents and creatives for testing |
| POST | `/api/workspaces/demo` | Create a private, seeded demo workspace → `{workspace_id, token}` |
| POST | `/api/workspaces` | Create an empty workspace `{name, brand_name}` |

## Workspace

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `` | any | Summary: counts, palette, tone, AI status |
| PUT | `/settings` | admin | Tone checks and palette |
| GET | `/events?submission_id=&limit=` | any | Append-only activity log |
| GET | `/analytics?include_samples=` | any | Brand Drift report |
| POST | `/visual/inspect` (multipart `file`) | any | Palette and contrast inspection |
| POST | `/visual/contrast` `{foreground, background}` | any | Exact WCAG ratio |

## Knowledge

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/knowledge/sources` | any | Documents and versions |
| GET | `/knowledge/sources/{id}` | any | Chunks, proposed rules, flags, other versions |
| POST | `/knowledge/sources` (multipart: `file`, `title`, `authority`, `effective_date`, `replaces_source_id`) | admin | Upload → pending review |
| POST | `/knowledge/sources/{id}/approve` `{accept_proposals: [int]}` | admin | Approve (supersedes previous version) |
| POST | `/knowledge/sources/{id}/reject` | admin | Reject pending source |
| GET | `/knowledge/sources/{id}/compare/{other}` | any | Section-level version comparison |
| GET / POST | `/knowledge/facts` | any / admin | List / add approved fact |
| POST | `/knowledge/facts/{id}/supersede` | admin | New fact version; old one superseded |
| PATCH | `/knowledge/facts/{id}` `{status}` | admin | Change status |
| GET / POST | `/knowledge/terms` | any / admin | List / add rule |
| PATCH | `/knowledge/terms/{id}` `{status}` | admin | Enable/disable rule |
| GET | `/knowledge/evidence/{evidence_id}` | any | Open a cited source with context (404 if it does not exist) |

## Submissions

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/submissions?status=` | any | List with latest audit summary |
| POST | `/submissions` `{title, channel, text, run_audit}` | creator/admin | Create (and audit) |
| GET | `/submissions/{id}` | any | Versions, findings, runs, comments, decisions, corrections |
| POST | `/submissions/{id}/audit` | any | Audit the latest version |
| PUT | `/submissions/{id}/content` `{text, note}` | creator/admin | Save edit as a new version |
| POST | `/submissions/{id}/findings/{fid}/accept` `{edited_text?}` | creator/admin | Apply suggestion or edit → new version |
| POST | `/submissions/{id}/findings/{fid}/reject` `{reason}` | any | Reject; original kept |
| POST | `/submissions/{id}/comments` `{body, finding_id?}` | any | Comment |
| POST | `/submissions/{id}/transition` `{action: submit\|request_changes\|approve, note}` | per action | Workflow decision |
| GET | `/submissions/{id}/diff?frm=&to=` | any | Word-level diff between versions |

### Finding object

```json
{
  "id": "FND-…", "rule_id": "OUTDATED-battery_life", "category": "fact", "severity": "high",
  "title": "Outdated specification “10 hours”", "passage": "10 hours", "start": 49, "end": 57,
  "explanation": "…", "evidence_status": "outdated",
  "evidence": [{"id": "FACT-…", "type": "fact", "role": "current", "document": "Northstar Product Spec Sheet v2",
                "version": 2, "page": 1, "section": "Northstar Beacon", "excerpt": "…", "status": "approved"}],
  "confidence": "high", "suggestion": "12 hours", "suggestion_reason": "…", "origin": "retrieval", "status": "open"
}
```
`evidence_status` ∈ `rule_violation`, `verified_conflict`, `outdated`, `unsupported`, `ambiguous`, `security`, `contextual`.
