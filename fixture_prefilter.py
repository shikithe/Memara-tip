#!/usr/bin/env python3
"""MemaraSix: conservative fixture prefilter. No predictions or ticket publishing."""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

YOUTH = re.compile(r"(?<!\w)(?:u[- ]?(?:1[5-9]|2[0-3])|youth|junior|primavera|juvenil|academy|under[- ]?\d+)(?!\w)", re.I)
RESERVE = re.compile(r"(?<!\w)(?:reserves?|reserve league|b[- ]team|ii)(?!\w)", re.I)
FRIENDLY = re.compile(r"friendly|friendlies|club friendlies|amical", re.I)
WOMEN = re.compile(r"(?<!\w)(?:women|woman|femenin[oa]|feminin|frauen|damen|femminile|wfc)(?!\w)", re.I)

def parse_utc(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None

def classify(fixture, now, buffer_minutes):
    reasons = []
    home = str(fixture.get("home") or "")
    away = str(fixture.get("away") or "")
    league = str(fixture.get("league_name") or "")
    label = " ".join((league, home, away))
    start = parse_utc(fixture.get("start_utc"))
    if not fixture.get("fixture_id") or not home or not away or not start:
        return "rejected", ["missing_identity_or_kickoff"]
    if start <= now + timedelta(minutes=buffer_minutes):
        return "rejected", ["kickoff_too_close_or_started"]
    if YOUTH.search(label):
        return "rejected", ["youth_competition"]
    if RESERVE.search(label):
        return "rejected", ["reserve_competition"]
    if FRIENDLY.search(label):
        return "rejected", ["friendly_competition"]
    if WOMEN.search(label):
        return "review", ["women_competition_separate_track"]
    # Fixture feed does not establish statistical coverage or odds.
    return "review", ["statistics_coverage_unverified", "odds_unverified"]

def build(doc, now, buffer_minutes=60):
    fixtures = (doc.get("football") or {}).get("fixtures") or []
    seen = set()
    rows = []
    for f in fixtures:
        key = f.get("fixture_id")
        if key in seen:
            state, reasons = "rejected", ["duplicate_fixture_id"]
        else:
            state, reasons = classify(f, now, buffer_minutes)
            if key is not None:
                seen.add(key)
        rows.append({
            "fixture_id": key, "league": f.get("league_name"),
            "home": f.get("home"), "away": f.get("away"),
            "start_utc": f.get("start_utc"),
            "decision": state, "reasons": reasons,
            "statistical_score": None, "odds": None
        })
    counts = {s: sum(x["decision"] == s for x in rows) for s in ("passed", "review", "rejected")}
    return {
        "date": doc.get("date"), "evaluated_at_utc": now.isoformat(),
        "input_count": len(fixtures), "counts": counts,
        "note": "Only metadata filtering; no team form or bookmaker odds checked. 'review' is not a betting recommendation.",
        "publication_allowed": False, "fixtures": rows
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="collector-output/statistics-research.json")
    p.add_argument("--output", default="collector-output/fixture-prefilter.json")
    p.add_argument("--buffer-minutes", type=int, default=60)
    p.add_argument("--now-utc", help="ISO timestamp for reproducible testing")
    a = p.parse_args()
    if not 0 <= a.buffer_minutes <= 1440:
        p.error("--buffer-minutes must be between 0 and 1440")
    now = parse_utc(a.now_utc) if a.now_utc else datetime.now(timezone.utc)
    if now is None:
        p.error("--now-utc must include timezone")
    doc = json.loads(Path(a.input).read_text(encoding="utf-8"))
    report = build(doc, now, a.buffer_minutes)
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(dest), "counts": report["counts"]}))

if __name__ == "__main__":
    main()
