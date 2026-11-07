"""Brand Drift Intelligence: aggregates computed only from stored findings, corrections and decisions."""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Correction, Finding, ReviewDecision, Submission
from .text_utils import normalise_passage

MIN_DECISIONS_FOR_CLARITY = 2


def drift_report(db: Session, workspace_id: str, include_samples: bool = True) -> dict:
    subs = {s.id: s for s in db.scalars(select(Submission).where(Submission.workspace_id == workspace_id))}
    if not include_samples:
        subs = {k: v for k, v in subs.items() if not v.is_sample}
    sample_count = sum(1 for s in subs.values() if s.is_sample)
    findings = [f for f in db.scalars(select(Finding).where(Finding.workspace_id == workspace_id)) if f.submission_id in subs]

    # de-duplicate re-audits: one occurrence per (submission, rule, passage)
    unique: dict[tuple, Finding] = {}
    for f in sorted(findings, key=lambda x: x.created_at):
        unique.setdefault((f.submission_id, f.rule_id, normalise_passage(f.passage)), f)
    uf = list(unique.values())

    by_sev = Counter(f.severity for f in uf)
    by_cat = Counter(f.category for f in uf)
    by_channel = Counter(f.channel for f in uf)
    by_evidence = Counter(f.evidence_status for f in uf)

    rules: dict[str, dict] = {}
    for f in uf:
        r = rules.setdefault(f.rule_id, {"rule_id": f.rule_id, "label": f.rule_label or f.title, "category": f.category,
                                         "count": 0, "submissions": set(), "channels": set()})
        r["count"] += 1
        r["submissions"].add(f.submission_id)
        r["channels"].add(f.channel)
    top_rules = sorted(rules.values(), key=lambda r: (-r["count"], r["label"]))[:10]
    for r in top_rules:
        r["submissions"] = len(r["submissions"])
        r["channels"] = sorted(r["channels"])

    term_counter = Counter(f.passage.strip().lower() for f in uf if f.category in ("terminology", "brand_name", "tone")
                           and f.origin == "rule")
    claim_counter = Counter(normalise_passage(f.passage) for f in uf if f.evidence_status in ("unsupported", "ambiguous"))

    corrections = [c for c in db.scalars(select(Correction)) if c.submission_id in subs]
    corr_counts = Counter(c.action for c in corrections)
    finding_by_id = {f.id: f for f in findings}
    per_rule = defaultdict(lambda: Counter())
    for c in corrections:
        f = finding_by_id.get(c.finding_id)
        if f:
            per_rule[(f.rule_id, f.rule_label or f.title)][c.action] += 1
    clarity = []
    for (rid, label), cnt in per_rule.items():
        total = sum(cnt.values())
        if total >= MIN_DECISIONS_FOR_CLARITY and cnt["rejected"] / total >= 0.5:
            clarity.append({"rule_id": rid, "label": label, "decisions": total, "rejected": cnt["rejected"],
                            "reason": "Creators dismissed this rule's findings in at least half of decisions — the rule may be unclear or too broad."})
    rule_repeat = [{"rule_id": r["rule_id"], "label": r["label"], "count": r["count"], "submissions": r["submissions"],
                    "reason": "Triggered across multiple submissions — consider creator training or clearer guidance."}
                   for r in top_rules if r["submissions"] >= 2]

    trend = Counter(f.created_at.date().isoformat() for f in uf)
    decisions = [d for d in db.scalars(select(ReviewDecision)) if d.submission_id in subs]

    channel_matrix: dict[str, Counter] = defaultdict(Counter)
    for f in uf:
        channel_matrix[f.channel][f.category] += 1

    return {
        "scope": {"include_samples": include_samples, "submissions": len(subs), "synthetic_samples": sample_count},
        "totals": {
            "submissions": len(subs),
            "audited_submissions": len({f.submission_id for f in findings}) if findings else 0,
            "findings": len(uf),
            "open_findings": sum(1 for f in findings if f.status == "open"),
            "approved_submissions": sum(1 for s in subs.values() if s.status == "approved"),
            "in_review": sum(1 for s in subs.values() if s.status in ("under_review", "revised")),
        },
        "by_severity": {k: by_sev.get(k, 0) for k in ("critical", "high", "medium", "low")},
        "by_category": dict(by_cat.most_common()),
        "by_channel": dict(by_channel.most_common()),
        "by_evidence_status": dict(by_evidence.most_common()),
        "channel_matrix": {ch: dict(c) for ch, c in channel_matrix.items()},
        "top_rules": top_rules,
        "repeated_terms": [{"term": t, "count": c} for t, c in term_counter.most_common(8)],
        "recurring_unsupported_claims": [{"claim": t, "count": c} for t, c in claim_counter.most_common(8)],
        "corrections": {"accepted": corr_counts.get("accepted", 0), "edited": corr_counts.get("edited", 0),
                        "rejected": corr_counts.get("rejected", 0)},
        "decisions": dict(Counter(d.decision for d in decisions)),
        "guideline_clarity_signals": clarity,
        "training_signals": rule_repeat,
        "trend": [{"date": d, "findings": c} for d, c in sorted(trend.items())],
        "notes": [
            "Counts include each issue once per submission, even if the submission was re-audited.",
            f"Clarity signals require at least {MIN_DECISIONS_FOR_CLARITY} creator decisions on a rule.",
        ],
    }
