"""Detection quality on the synthetic Northstar test set (judge test cases 1-9, 15)."""
from app.seed.northstar import SAMPLES

S = {s["key"]: s for s in SAMPLES}


def rules(d):
    return {f["rule_id"].split("-")[0] for f in d["findings"]}


def titles(d):
    return " | ".join(f["title"] for f in d["findings"])


def test_compliant_sample_has_no_invented_findings(ws):  # TC3, TC6
    d = ws.audit_text(S["compliant"]["text"])
    assert d["findings"] == [], titles(d)
    verified = {v["passage"] for v in d["latest_audit"]["verified_claims"]}
    assert {"40+ apps", "12 languages", "30%"} <= verified
    for v in d["latest_audit"]["verified_claims"]:
        assert v["evidence"] and v["evidence"][0]["id"].startswith("FACT-")


def test_unsupported_claims_are_unable_to_verify(ws):  # TC4
    d = ws.audit_text(S["unsupported"]["text"], "advertisement")
    by = {f["passage"]: f for f in d["findings"]}
    assert "by 50%" in by and "the best solution in the market" in by
    for f in d["findings"]:
        assert f["evidence_status"] == "unsupported"
        assert "Unable to verify against approved knowledge" in f["explanation"]
        assert "not proof that the claim is false" in f["explanation"]


def test_prohibited_preferred_and_brand_name_terms(ws):  # TC1, TC2
    d = ws.audit_text(S["terminology"]["text"], "instagram")
    passages = {f["passage"] for f in d["findings"]}
    assert {"NorthStar Pulse", "game-changing", "Log in", "deep work mode", "cheap"} <= passages
    assert any("#NorthstarLabs" in f["title"] for f in d["findings"])
    sugg = {f["passage"]: f["suggestion"] for f in d["findings"]}
    assert sugg["cheap"] == "affordable" and sugg["Log in"] == "Sign in" and sugg["NorthStar Pulse"] == "Northstar Pulse"


def test_channel_rule_only_applies_to_its_channel(ws):
    d = ws.audit_text(S["terminology"]["text"], "website")
    assert not any("#NorthstarLabs" in f["title"] for f in d["findings"])


def test_word_boundaries_avoid_false_positives(ws):
    d = ws.audit_text("Our cheapest-looking blog intro is cheaply made by a catalogue team. Login-page redesign is live.")
    assert not [f for f in d["findings"] if f["passage"].lower() in ("cheap", "log in")], titles(d)


def test_outdated_specification_detected_with_current_fact(ws):  # TC5 (version conflict)
    d = ws.audit_text(S["outdated"]["text"])
    out = [f for f in d["findings"] if f["evidence_status"] == "outdated"]
    assert len(out) == 1 and out[0]["passage"] == "10 hours" and out[0]["suggestion"] == "12 hours"
    roles = {e["role"] for e in out[0]["evidence"]}
    assert roles == {"current", "superseded"}
    assert any(v["passage"] == "90 minutes" for v in d["latest_audit"]["verified_claims"])


def test_conflicting_approved_facts(ws):  # TC5
    d = ws.audit_text(S["conflict"]["text"], "presentation")
    conf = {f["passage"]: f["suggestion"] for f in d["findings"] if f["evidence_status"] == "verified_conflict"}
    assert conf == {"25 apps": "40+ apps", "20 languages": "12 languages", "$6": "$8"}


def test_forbidden_claims_discount_limit_and_tone(ws):
    d = ws.audit_text(S["risky"]["text"], "email")
    ps = {f["passage"]: f for f in d["findings"]}
    assert ps["100% secure"]["severity"] == "critical" and ps["HIPAA certified"]["severity"] == "critical"
    assert "40%" in ps and ps["40%"]["suggestion"] == "25%"
    assert "!!!" in ps
    assert not any(f["rule_id"].startswith("UNSUPPORTED") and f["passage"] == "100%" for f in d["findings"])


def test_every_citation_points_to_a_real_source(ws):  # TC8
    for s in SAMPLES:
        d = ws.audit_text(s["text"], s["channel"])
        for f in d["findings"]:
            for e in f["evidence"]:
                if e["type"] in ("fact", "chunk", "term"):
                    r = ws.get(f"/knowledge/evidence/{e['id']}")
                    assert r.status_code == 200, (e, r.text)
                    assert r.json()["excerpt"] == e["excerpt"]


def test_rule_findings_cite_document_and_page(ws):
    d = ws.audit_text("Get cheap plans today.")
    f = next(x for x in d["findings"] if x["passage"] == "cheap")
    ev = f["evidence"][0]
    assert ev["document"] == "Northstar Labs Brand Guidelines v3" and ev["page"] == 2 and ev["section"] == "3. Terminology"


def test_suggestions_are_minimal_and_preserve_meaning(ws):  # TC9
    d = ws.audit_text(S["conflict"]["text"], "presentation")
    for f in d["findings"]:
        assert f["suggestion"] is not None
        # the edit only touches the flagged passage and is short
        assert len(f["suggestion"]) <= len(f["passage"]) + 10


def test_prompt_injection_in_content_is_flagged_and_inert(ws):  # TC15
    d = ws.audit_text(S["injection"]["text"])
    sec = [f for f in d["findings"] if f["category"] == "security"]
    assert len(sec) == 1
    assert any(f["passage"] == "3x faster" for f in d["findings"])  # still audited normally


def test_injection_flagged_in_uploaded_document_and_not_auto_approved(ws):  # TC15
    from app.seed.northstar import GUIDELINES_V4_DRAFT
    r = ws.post("/knowledge/sources", role="admin",
                files={"file": ("Northstar_Brand_Guidelines_v4_draft.txt", GUIDELINES_V4_DRAFT.encode(), "text/plain")},
                data={"title": "Northstar Labs Brand Guidelines v4"})
    assert r.status_code == 201, r.text
    src = r.json()
    assert src["status"] == "pending_review"
    assert src["injection_flags"], "embedded instruction should be flagged"
    # pending knowledge is not used as evidence
    d = ws.audit_text("Get 22% off this week.")
    assert not any(f["rule_id"].startswith("TERM") and "20%" in f["title"] for f in d["findings"])
    kinds = {(p["kind"], p["term"]) for p in src["proposed_rules"]}
    assert ("preferred", "teammates") in kinds and ("prohibited", "hustle") in kinds
