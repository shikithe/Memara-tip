#!/usr/bin/env python3
"""Fail-closed contract: MemaraSix publishes only after a dated AI approval.

The approval's declared source is policy metadata, not a cryptographic signature.
Repository write permissions / branch protection must restrict who can edit it.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from memarasix_sync_listasix import canonical_hash

SAR = ZoneInfo("Europe/Sarajevo")


def as_utc(value):
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Timestamps must have timezones")
    return stamp.astimezone(timezone.utc)


def valid_approval(active, history, receipt, approved, now):
    today = now.astimezone(SAR).date().isoformat()
    if not isinstance(active, dict) or not isinstance(history, dict):
        raise ValueError("Synchronized ListaSix files are missing")
    if any(obj.get("date") != today for obj in (active, history, receipt, approved)):
        raise ValueError("Ready data, receipt and AI approval must all be for today")
    if not active.get("publication_allowed") or not active.get("fixtures"):
        raise ValueError("Synchronized ListaSix data not publishable")
    if not history.get("fixtures") or not history.get("leagues"):
        raise ValueError("Synchronized ListaSix history incomplete")
    if as_utc(active.get("expires_at")) <= now:
        raise ValueError("Synchronized ListaSix list expired")
    source_hash = canonical_hash(active)
    if receipt.get("active_sha256") != source_hash:
        raise ValueError("Receipt hash does not match synchronized ListaSix data")
    if approved.get("source_active_sha256") != source_hash:
        raise ValueError("AI did not approve this exact version of ListaSix data")
    if approved.get("approval_source") != "chatgpt_ai_analyst":
        raise ValueError("Only the ChatGPT AI analyst can submit an approval")
    if approved.get("publication_allowed") is not True:
        raise ValueError("AI has not allowed this publication")
    ready_at = as_utc(receipt.get("synced_at_utc"))
    approved_at = as_utc(approved.get("approved_at_utc"))
    if not (ready_at <= approved_at <= now + timedelta(minutes=5)):
        raise ValueError("AI approval must be after confirmed receipt, not in the future")
    if approved_at.astimezone(SAR).date().isoformat() != today:
        raise ValueError("AI approval timestamp is not today")
    entries = approved.get("tickets")
    if not isinstance(entries, list) or not entries:
        raise ValueError("No AI-approved tickets")
    ids, used = set(), set()
    available = {row.get("fixture_id"): row for row in active["fixtures"]
                 if isinstance(row, dict) and row.get("fixture_id")}
    for ticket in entries:
        if not isinstance(ticket, dict):
            raise ValueError("Malformed AI-approved ticket")
        tid = ticket.get("id")
        if tid not in {"A", "B", "C"} or tid in ids:
            raise ValueError("Invalid/duplicated AI ticket ID")
        ids.add(tid)
        if not isinstance(ticket.get("analysis"), str) or len(ticket["analysis"].strip()) < 40:
            raise ValueError("Missing substantive independent AI analysis")
        legs = ticket.get("matches")
        if not isinstance(legs, list) or not legs:
            raise ValueError("Ticket has no legs")
        odd_product = 1.0
        for leg in legs:
            if not isinstance(leg, dict):
                raise ValueError("Malformed approved leg")
            fid = leg.get("fixture_id")
            if not fid or fid in used or fid not in available:
                raise ValueError("Unknown or duplicated approved fixture ID")
            used.add(fid)
            start = as_utc(available[fid]["datetime"])
            if start <= now + timedelta(minutes=20):
                raise ValueError("Approved fixture already started or begins too soon")
            pick = leg.get("pick")
            if pick not in {"1", "2", "2+", "3+", "GG", "NG"}:
                raise ValueError("Unknown approved market")
            if tid == "B" and pick != "3+":
                raise ValueError("Ticket B can contain only over 2.5")
            if not leg.get("bookmaker"):
                raise ValueError("No verified quote source")
            try:
                odd = float(leg["odd"])
            except (KeyError, ValueError, TypeError):
                raise ValueError("No valid decimal odds")
            if not 1.01 < odd < 50:
                raise ValueError("Invalid decimal odd")
            odd_product *= odd
        if tid in {"A", "B"} and not 2.0 <= odd_product <= 3.0:
            raise ValueError("A/B must each total 2.00–3.00")
        if tid == "C" and odd_product < 10:
            raise ValueError("C must total at least 10")
    return {"date": today, "source_active_sha256": source_hash,
            "approved_at_utc": approved_at.isoformat(), "tickets": sorted(ids)}


def check_files(root, now):
    try:
        def read(name):
            return json.loads((root / name).read_text(encoding="utf-8"))
        return valid_approval(
            read("listasix-data/active-list.json"),
            read("listasix-data/history-h2h.json"),
            read("listasix-data/sync-receipt.json"),
            read("memarasix-1455-approved.json"),
            now,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(str(exc)) from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-publishable", action="store_true")
    args = parser.parse_args()
    try:
        checked = check_files(Path("."), datetime.now(timezone.utc))
    except ValueError as exc:
        print("AI_APPROVAL_NOT_READY", str(exc))
        return 1 if args.require_publishable else 0
    print("AI_APPROVAL_READY_TO_PUBLISH", json.dumps(checked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
