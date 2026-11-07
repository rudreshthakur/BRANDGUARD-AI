"""Run the labelled synthetic evaluation set through the real audit engine and report precision/recall.

Usage (from backend/):  python -m eval.run_eval
A flagged passage counts as a true positive only if its passage AND evidence status match an expected item.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp()) / 'eval.db'}")
os.environ.setdefault("BRANDGUARD_LLM_PROVIDER", "none")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import ContentVersion, Finding, Submission  # noqa: E402
from app.seed.northstar import create_workspace, seed_northstar  # noqa: E402
from app.services.auditor import run_audit  # noqa: E402
from sqlalchemy import select  # noqa: E402


def main() -> int:
    data = json.loads((Path(__file__).parent / "eval_set.json").read_text())
    Base.metadata.create_all(engine)
    db = SessionLocal()
    ws, _ = create_workspace(db, "eval", "Northstar Labs", True)
    db.commit()
    seed_northstar(db, ws, with_activity=False)
    tp = fp = fn = 0
    vtp = vfn = 0
    status_ok = 0
    clean_items = clean_pass = 0
    rows = []
    for item in data["items"]:
        sub = Submission(workspace_id=ws.id, title=item["id"], channel=item["channel"])
        db.add(sub)
        db.flush()
        v = ContentVersion(submission_id=sub.id, version_no=1, text=item["text"])
        db.add(v)
        sub.versions.append(v)
        db.commit()
        run = run_audit(db, ws, sub, "creator")
        found = [(f.passage, f.evidence_status) for f in db.scalars(select(Finding).where(Finding.audit_run_id == run.id))]
        expected = [tuple(e) for e in item["expect"]]
        found_passages = {p for p, _ in found}
        exp_passages = {p for p, _ in expected}
        i_tp = sum(1 for e in expected if e in found)
        i_fn = len(expected) - i_tp
        i_fp = sum(1 for f in found if f not in expected)
        status_ok += sum(1 for p, s in expected if p in found_passages and (p, s) in found)
        tp, fp, fn = tp + i_tp, fp + i_fp, fn + i_fn
        verified = {c["passage"] for c in run.verified_claims}
        vtp += sum(1 for x in item["verify"] if x in verified)
        vfn += sum(1 for x in item["verify"] if x not in verified)
        if not expected:
            clean_items += 1
            clean_pass += int(not found)
        ok = i_fn == 0 and i_fp == 0
        rows.append((item["id"], ok, i_tp, i_fp, i_fn, sorted(found_passages - exp_passages), sorted(exp_passages - found_passages)))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    print("item  pass  tp fp fn  unexpected / missed")
    for r in rows:
        print(f"{r[0]:5} {'PASS' if r[1] else 'FAIL':5} {r[2]:2} {r[3]:2} {r[4]:2}  {r[5] or ''} {r[6] or ''}")
    print(f"\nItems: {len(rows)}  fully correct: {sum(1 for r in rows if r[1])}")
    print(f"Expected issues: {tp + fn}  true positives: {tp}  false positives: {fp}  false negatives: {fn}")
    print(f"Issue precision: {precision:.2f}  Issue recall: {recall:.2f}")
    print(f"Compliant items with zero findings: {clean_pass}/{clean_items}")
    print(f"Approved claims verified: {vtp}/{vtp + vfn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
