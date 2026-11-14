"""Bounded report content copied from published case and finding records."""
from collections import Counter

from cases.repository import utc_now


def analyst_text(value):
    if value is None:
        return ""
    value = value.strip()
    if len(value) > 2000 or any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in value):
        raise ValueError("Analyst text must be at most 2000 characters without control characters")
    return value


def audit_snapshot(cases, case_id):
    cutoff = utc_now()
    events, cursor = cases.query_events(case_id, to_at=cutoff, limit=500)
    # Keep descriptive audit fields; arbitrary event payloads are not report content.
    items = [{key: event[key] for key in ("id", "type", "actor", "created_at", "summary", "evidence_id", "run_id")}
             for event in reversed(events)]
    return {"scope": "case-wide", "captured_at": cutoff, "included_count": len(items),
            "counts_by_type": dict(sorted(Counter(item["type"] for item in items).items())),
            "truncated": cursor is not None, "limit": 500, "events": items,
            "limitations": ["Application-recorded events only; not a complete pre-submission chain of custody.",
                            "Actor names are self-declared. This log is not independently tamper-proof.",
                            "The latest 500 case events are retained; event counts describe included events only.",
                            "Audit scope is case-wide and may include events for unselected runs."]}
