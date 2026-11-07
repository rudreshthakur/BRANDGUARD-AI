"""Corrections, versions and the human approval workflow (judge test cases 10-14)."""
from app.seed.northstar import SAMPLES

S = {s["key"]: s for s in SAMPLES}


def _find(d, passage):
    return next(f for f in d["findings"] if f["passage"] == passage)


def test_accept_creates_new_version_and_preserves_original(ws):  # TC10
    d = ws.audit_text(S["conflict"]["text"], "presentation")
    f = _find(d, "25 apps")
    r = ws.post(f"/submissions/{d['id']}/findings/{f['id']}/accept", json={})
    assert r.status_code == 200, r.text
    d2 = r.json()
    assert d2["current_version"] == 2
    assert d2["versions"][0]["text"] == S["conflict"]["text"]
    assert "40+ apps" in d2["versions"][1]["text"] and "25 apps" not in d2["versions"][1]["text"]
    # other findings in the same run shifted correctly and can still be applied
    f2 = _find(d2, "20 languages")
    assert d2["versions"][1]["text"][f2["start"]:f2["end"]] == "20 languages"
    d3 = ws.post(f"/submissions/{d['id']}/findings/{f2['id']}/accept", json={}).json()
    assert d3["versions"][-1]["text"] == "Northstar Pulse integrates with 40+ apps, supports 12 languages, and the Team plan costs $6 per user per month."
    assert len(d3["corrections"]) == 2


def test_edit_applies_creator_text(ws):
    d = ws.audit_text("Get cheap plans today.")
    f = _find(d, "cheap")
    d2 = ws.post(f"/submissions/{d['id']}/findings/{f['id']}/accept", json={"edited_text": "budget-friendly"}).json()
    assert d2["versions"][-1]["text"] == "Get budget-friendly plans today."
    assert d2["corrections"][0]["action"] == "edited"


def test_removal_suggestion_tidies_spacing(ws):
    d = ws.audit_text(S["unsupported"]["text"], "advertisement")
    f = _find(d, "by 50%")
    d2 = ws.post(f"/submissions/{d['id']}/findings/{f['id']}/accept", json={}).json()
    assert d2["versions"][-1]["text"].startswith("Our new product improves productivity and is")


def test_reject_preserves_original(ws):  # TC11
    d = ws.audit_text("Get cheap plans today.")
    f = _find(d, "cheap")
    d2 = ws.post(f"/submissions/{d['id']}/findings/{f['id']}/reject", json={"reason": "Approved by legal"}).json()
    assert d2["current_version"] == 1 and d2["versions"][0]["text"] == "Get cheap plans today."
    assert _find(d2, "cheap")["status"] == "rejected"
    assert any("Approved by legal" in c["body"] for c in d2["comments"])


def test_full_review_loop(ws):  # TC12, TC13, TC14
    d = ws.audit_text(S["outdated"]["text"])
    sid = d["id"]
    # creator cannot approve; reviewer cannot submit
    assert ws.post(f"/submissions/{sid}/transition", role="creator", json={"action": "approve"}).status_code == 403
    assert ws.post(f"/submissions/{sid}/transition", role="reviewer", json={"action": "submit"}).status_code == 403
    assert ws.post(f"/submissions/{sid}/transition", json={"action": "submit"}).json()["status"] == "under_review"
    # locked while under review
    f = _find(d, "10 hours")
    assert ws.post(f"/submissions/{sid}/findings/{f['id']}/accept", json={}).status_code == 409
    # request changes requires a note
    assert ws.post(f"/submissions/{sid}/transition", role="reviewer", json={"action": "request_changes"}).status_code == 422
    d = ws.post(f"/submissions/{sid}/transition", role="reviewer", json={"action": "request_changes", "note": "Battery spec is outdated."}).json()
    assert d["status"] == "changes_requested"
    d = ws.post(f"/submissions/{sid}/findings/{f['id']}/accept", json={}).json()
    # resubmission requires an audit of the latest version
    assert ws.post(f"/submissions/{sid}/transition", json={"action": "submit"}).status_code == 409
    ws.post(f"/submissions/{sid}/audit")
    d = ws.post(f"/submissions/{sid}/transition", json={"action": "submit"}).json()
    assert d["status"] == "revised"
    d = ws.post(f"/submissions/{sid}/transition", role="reviewer", json={"action": "approve", "note": "Looks right."}).json()
    assert d["status"] == "approved"
    assert [x["decision"] for x in d["decisions"]] == ["submitted", "changes_requested", "resubmitted", "approved"]
    assert len(d["versions"]) == 2
    events = ws.get(f"/events?submission_id={sid}").json()["events"]
    assert {"review.approved", "correction.accepted", "audit.run"} <= {e["action"] for e in events}


def test_approval_with_open_high_findings_requires_justification(ws):
    d = ws.audit_text(S["unsupported"]["text"], "advertisement")
    sid = d["id"]
    ws.post(f"/submissions/{sid}/transition", json={"action": "submit"})
    r = ws.post(f"/submissions/{sid}/transition", role="reviewer", json={"action": "approve"})
    assert r.status_code == 422 and "justification" in r.json()["detail"]
    r = ws.post(f"/submissions/{sid}/transition", role="reviewer",
                json={"action": "approve", "note": "Substantiation on file from Q3 study."})
    assert r.json()["status"] == "approved"
    assert r.json()["decisions"][-1]["open_findings_at_decision"] == 2


def test_editing_approved_content_requires_reapproval(ws):
    d = ws.audit_text(S["compliant"]["text"])
    sid = d["id"]
    ws.post(f"/submissions/{sid}/transition", json={"action": "submit"})
    ws.post(f"/submissions/{sid}/transition", role="reviewer", json={"action": "approve"})
    d = ws.put(f"/submissions/{sid}/content", json={"text": S["compliant"]["text"] + " New line."}).json()
    assert d["status"] == "draft" and d["current_version"] == 2


def test_diff_endpoint(ws):
    d = ws.audit_text("Get cheap plans today.")
    f = _find(d, "cheap")
    ws.post(f"/submissions/{d['id']}/findings/{f['id']}/accept", json={})
    ops = ws.get(f"/submissions/{d['id']}/diff?frm=1&to=2").json()["ops"]
    assert {"op": "delete", "text": "cheap"} in ops and {"op": "insert", "text": "affordable"} in ops
