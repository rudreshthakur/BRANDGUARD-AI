"""Knowledge management, evidence validation, AI validation, security, errors (TC7, TC15-18)."""
import io
import json

from app.services import llm


def test_health_and_status(client):
    assert client.get("/api/health").json()["database"] is True
    s = client.get("/api/system/status").json()
    assert s["ai"]["enabled"] is False  # TC16: no credentials -> still works


def test_missing_ai_credentials_do_not_crash_and_are_disclosed(ws):  # TC16
    d = ws.audit_text("Get cheap plans today.")
    assert d["latest_audit"]["ai_mode"] == "disabled"
    assert "unavailable" in d["latest_audit"]["ai_status"]
    assert all(f["origin"] != "ai" for f in d["findings"])


def test_workspace_isolation(client, ws):
    other = client.post("/api/workspaces/demo").json()
    r = client.get(f"/api/w/{other['workspace_id']}/submissions", headers=ws.h())
    assert r.status_code == 404
    assert client.get(f"/api/w/{ws.id}/submissions").status_code == 404


def test_role_permissions_on_knowledge(ws):
    body = {"kind": "prohibited", "term": "synergy", "replacement": "teamwork"}
    assert ws.post("/knowledge/terms", role="creator", json=body).status_code == 403
    assert ws.post("/knowledge/terms", role="admin", json=body).status_code == 201
    d = ws.audit_text("Real synergy for teams.")
    assert any(f["passage"] == "synergy" and f["suggestion"] == "teamwork" for f in d["findings"])


def test_superseding_a_fact_flags_old_value_as_outdated(ws):  # Round-3 foundation: versioned facts
    facts = ws.get("/knowledge/facts").json()["facts"]
    lang = next(f for f in facts if f["metric"] == "languages" and f["status"] == "approved")
    r = ws.post(f"/knowledge/facts/{lang['id']}/supersede", role="admin",
                json={"statement": "Northstar Pulse supports 15 languages.", "subject": "Northstar Pulse", "value": 15,
                      "unit": "languages", "keywords": ["languages", "supports"], "effective_date": "2026-11-01"})
    assert r.status_code == 201, r.text
    d = ws.audit_text("Pulse supports 12 languages.")
    f = next(x for x in d["findings"] if x["passage"] == "12 languages")
    assert f["evidence_status"] == "outdated" and f["suggestion"] == "15 languages"


def test_admin_fact_validation(ws):
    r = ws.post("/knowledge/facts", role="admin", json={"statement": "Pulse has 3 tiers.", "value": 3})
    assert r.status_code == 422


def test_invalid_evidence_ids_are_rejected(ws):  # TC7
    from app.db import SessionLocal
    from app.models import Workspace
    from app.services.auditor import build_context
    with SessionLocal() as db:
        w = db.get(Workspace, ws.id)
        ctx = build_context(db, w, "website")
        real = next(iter(ctx.retriever.by_id))
        rep = ctx.validator.validate([{"id": "FACT-DOESNOTEXIST"}, {"id": real}, {"id": "CHUNK-FAKE123"}])
        assert [e["id"] for e in rep.kept] == [real]
        assert {r["id"] for r in rep.rejected} == {"FACT-DOESNOTEXIST", "CHUNK-FAKE123"}
    assert ws.get("/knowledge/evidence/FACT-DOESNOTEXIST").status_code == 404


def test_ai_output_is_validated_against_content_and_retrieved_evidence(ws, monkeypatch):  # TC7, TC15
    monkeypatch.setattr(llm, "get_provider", lambda: llm.MockProvider())
    llm.MockProvider.next_response = json.dumps({"findings": [
        {"category": "tone", "severity": "medium", "passage": "Plan calmly with Pulse", "title": "Tone ok?",
         "explanation": "Brand voice is calm and practical.", "evidence_ids": ["FACT-INVENTED", "CHUNK-NOPE"],
         "suggestion": "Plan calmly with Northstar Pulse", "confidence": "high"},
        {"category": "claim", "severity": "high", "passage": "text that is not in the content", "title": "Hallucinated",
         "explanation": "x", "evidence_ids": [], "confidence": "high"},
    ]})
    d = ws.audit_text("Plan calmly with Pulse every week.")
    ai = [f for f in d["findings"] if f["origin"] == "ai"]
    assert len(ai) == 1, "non-verbatim passage must be dropped"
    assert ai[0]["evidence"] == [] and ai[0]["confidence"] == "low"
    assert "Unable to verify" in ai[0]["explanation"]
    assert "removed 1 finding" in d["latest_audit"]["ai_status"] and "2 invalid evidence" in d["latest_audit"]["ai_status"]


def test_malformed_ai_output_falls_back_gracefully(ws, monkeypatch):
    monkeypatch.setattr(llm, "get_provider", lambda: llm.MockProvider())
    llm.MockProvider.next_response = "Sure! Here are some thoughts, no JSON."
    d = ws.audit_text("Get cheap plans today.")
    assert "failed" in d["latest_audit"]["ai_status"]
    assert any(f["passage"] == "cheap" for f in d["findings"])


def test_unsupported_upload_formats(ws):  # TC18
    r = ws.post("/knowledge/sources", role="admin", files={"file": ("brand.exe", b"MZ\x90\x00", "application/octet-stream")})
    assert r.status_code == 415 and "Unsupported file type" in r.json()["detail"]
    r = ws.post("/knowledge/sources", role="admin", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 415
    r = ws.post("/knowledge/sources", role="admin", files={"file": ("empty.txt", b"", "text/plain")})
    assert r.status_code == 422
    r = ws.post("/visual/inspect", files={"file": ("x.png", b"definitely not an image", "image/png")})
    assert r.status_code == 415


def test_docx_and_pdf_ingestion_preserve_metadata(ws):
    import docx
    doc = docx.Document()
    doc.add_heading("Terminology", level=1)
    doc.add_paragraph('Use "members" instead of "subscribers" in all copy.')
    buf = io.BytesIO()
    doc.save(buf)
    r = ws.post("/knowledge/sources", role="admin", files={"file": ("terms.docx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 201, r.text
    src = r.json()
    assert src["chunks"][0]["section"] == "Terminology"
    assert src["proposed_rules"][0]["kind"] == "preferred"
    r = ws.post(f"/knowledge/sources/{src['id']}/approve", role="admin", json={"accept_proposals": [0]})
    assert r.json()["status"] == "approved"
    d = ws.audit_text("All subscribers get updates.")
    assert any(f["passage"] == "subscribers" and f["suggestion"] == "members" for f in d["findings"])
    pdf = ws.get("/knowledge/sources").json()["sources"]
    assert any(s["page_count"] == 4 for s in pdf)


def test_new_document_version_supersedes_previous(ws):
    srcs = ws.get("/knowledge/sources").json()["sources"]
    v1 = next(s for s in srcs if s["title"] == "Northstar Product Spec Sheet v1")
    assert v1["status"] == "superseded"
    v2 = next(s for s in srcs if s["title"] == "Northstar Product Spec Sheet v2")
    cmp = ws.get(f"/knowledge/sources/{v2['id']}/compare/{v1['id']}").json()
    assert any(c["change"] in ("modified", "added") for c in cmp["changes"])


def test_backend_errors_are_understandable(ws):  # TC17
    r = ws.post("/submissions", json={"title": "x", "channel": "website", "text": "   "})
    assert r.status_code == 422 and "empty" in r.json()["detail"].lower()
    r = ws.post("/submissions", json={"title": "x", "channel": "fax", "text": "hi"})
    assert r.status_code == 422 and "channel" in r.json()["detail"]
    r = ws.get("/submissions/SUB-NOPE")
    assert r.status_code == 404 and r.json()["detail"] == "Submission not found."
    r = ws.post("/submissions", json={"text": "x" * 25000})
    assert r.status_code == 422 and "exceeds" in r.json()["detail"]
    r = ws.c.post(f"/api/w/{ws.id}/submissions", headers={**ws.h(), "X-Demo-Role": "superuser"}, json={"text": "hi"})
    assert r.status_code == 400 and "Unknown role" in r.json()["detail"]


def test_visual_inspector_palette_and_contrast(ws):
    on = ws.c.get("/api/samples/files/northstar_onbrand_creative.png").content
    off = ws.c.get("/api/samples/files/northstar_offbrand_creative.png").content
    r_on = ws.post("/visual/inspect", files={"file": ("on.png", on, "image/png")}).json()
    r_off = ws.post("/visual/inspect", files={"file": ("off.png", off, "image/png")}).json()
    assert not [f for f in r_on["findings"] if f["id"].startswith("VIS-PALETTE")]
    off_ids = {f["id"].split("-")[1] for f in r_off["findings"]}
    assert "PALETTE" in off_ids and "CONTRAST" in off_ids
    assert all(f["needs_human_confirmation"] for f in r_off["findings"])
    pal = next(f for f in r_off["findings"] if f["id"].startswith("VIS-PALETTE"))
    assert pal["evidence"] and pal["evidence"][0]["type"] == "palette"
    c = ws.post("/visual/contrast", json={"foreground": "#000000", "background": "#FFFFFF"}).json()
    assert c["ratio"] == 21.0 and c["aa_normal"]


def test_brand_drift_uses_real_data_and_can_exclude_samples(ws):
    a = ws.get("/analytics?include_samples=true").json()
    assert a["scope"]["synthetic_samples"] == 5 and a["totals"]["findings"] > 0
    assert a["corrections"]["accepted"] == 1 and a["corrections"]["rejected"] == 1
    b = ws.get("/analytics?include_samples=false").json()
    assert b["totals"]["findings"] == 0
    ws.audit_text("Get cheap plans today.")
    ws.audit_text("Cheap and cheerful.")
    c = ws.get("/analytics?include_samples=false").json()
    assert c["repeated_terms"][0] == {"term": "cheap", "count": 2}
    assert c["training_signals"] and c["training_signals"][0]["submissions"] == 2


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
