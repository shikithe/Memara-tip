#!/usr/bin/env python3
"""AI approval transcription publisher for football A/B.
No ESPN lookup, match identification, market selection or odds verification.
"""
import json
import math
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

SAR = ZoneInfo("Europe/Sarajevo")
FEED_URL = "https://raw.githubusercontent.com/shikithe/Slavojka/main/shared/collector-feed.json"
APPROVAL = "memarasix-football-ai-approved.json"

def utc(value):
    v = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if v.tzinfo is None:
        raise ValueError("timestamp must contain timezone")
    return v.astimezone(timezone.utc)

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write(path, obj):
    dest = Path(path)
    temp = dest.with_name(dest.name + ".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(dest)

def verify(approval, feed, current, now):
    """Pass through AI-selected tickets unchanged. No ESPN or bookmaker lookup."""
    today = now.astimezone(SAR).date().isoformat()
    if approval.get("date") != today:
        raise ValueError("approval is not for today")
    if approval.get("approval_source") != "chatgpt_ai_analyst" or approval.get("publication_allowed") is not True:
        raise ValueError("AI approval is missing")
    approved_at = utc(approval["approved_at_utc"])
    if approved_at.astimezone(SAR).date().isoformat() != today or approved_at > now + timedelta(minutes=5):
        raise ValueError("invalid approval timestamp")
    tickets = approval.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        raise ValueError("no approved A/B tickets")
    same_day = current.get("date") == today
    existing = current.get("tickets", []) if same_day else []
    ids = {t.get("id") for t in existing}
    seen = set()
    selections = []
    for ticket in tickets:
        if not isinstance(ticket, dict):
            raise ValueError("malformed approved ticket")
        tid = ticket.get("id")
        if tid not in ("A", "B") or tid in seen:
            raise ValueError("duplicate or invalid ticket identifier")
        seen.add(tid)
        if tid in ids:
            continue
        if not isinstance(ticket.get("matches"), list) or not ticket["matches"]:
            raise ValueError("approved ticket has no matches")
        if not isinstance(ticket.get("analysis"), str):
            raise ValueError("missing AI analysis")
        # Preserve every AI-supplied selection, team, market, price, time, and description.
        # Only append publisher-owned metadata later.
        selections.append(dict(ticket))
    return selections

def publish(root=Path("."), now=None, feed=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(SAR).date().isoformat()
    current = read(root/"data.json")
    approval = read(root/APPROVAL)
    if current.get("date") != today and (current.get("date", "") > today or not current.get("settled", False)):
        raise ValueError("prior bank not settled or future-dated")
    selections = verify(approval, None, current, now)
    if not selections:
        return {"status":"no_update", "reason":"A/B already published"}
    same_day = current.get("date") == today
    existing = list(current.get("tickets", [])) if same_day else []
    bank = float(current.get("bank_before", current.get("bank_after", 0)) if same_day else current.get("bank_after", 0))
    balance = float(current.get("bank_after", 0))
    if bank <= 0 or balance <= 0:
        raise ValueError("invalid bank")
    # The user's bank rule reserves 1.5% of STARTING daily bank for NBA C.
    # A/B may spend at most 8.5% together; never absorb C's reserve.
    opening_bank = Decimal(str(bank))
    cent = Decimal("0.01")
    daily_cap = (opening_bank * Decimal("0.10")).quantize(cent, rounding=ROUND_FLOOR)
    nba_reserve = (opening_bank * Decimal("0.015")).quantize(cent, rounding=ROUND_CEILING)
    budget = float(daily_cap)
    c_reserved = float(nba_reserve)
    football_budget = float(max(Decimal(0), daily_cap - nba_reserve))
    spent = round(sum(float(t.get("stake", 0)) for t in existing), 2)
    spent_ab = round(sum(float(t.get("stake", 0)) for t in existing
                         if t.get("id") in ("A", "B")), 2)
    # Preserve historic A:B 65:25 ratio, scaled proportionally into 8.5%.
    shares = {"A": 65.0 / 90.0, "B": 25.0 / 90.0}
    added = 0.
    for t in selections:
        stake = round(football_budget * shares[t["id"]], 2)
        if (stake <= 0
                or round(spent_ab + added + stake, 2) > football_budget + .001
                or round(spent + added + stake, 2) > budget + .001
                or balance < added + stake):
            raise ValueError("insufficient A/B stake budget; NBA C reserve protected")
        t.update({"stake": stake, "status": "objavljen", "payout": 0})
        added = round(added + stake, 2)
    statuses = dict(current.get("pending_ticket_statuses", {})) if same_day else {}
    reasons = dict(current.get("pending_ticket_reasons", {})) if same_day else {}
    for t in selections:
        statuses[t["id"]] = "objavljen"
        reasons[t["id"]] = ""
    current.update({
        "date": today,
        "published": current.get("published") if existing else now.astimezone(SAR).strftime("%d.%m.%Y. u %H:%M (Europe/Sarajevo)"),
        "published_at_utc": current.get("published_at_utc") if existing else now.isoformat(),
        "publication_type": "independent_ai_espn_only_github_publisher",
        "bank_before": bank, "daily_budget": budget,
        "football_ab_budget": football_budget, "reserved_nba_c_budget": c_reserved,
        "daily_stake": round(spent+added, 2),
        "bank_after": round(balance-added, 2),
        "bank_after_stakes": round(balance-added, 2),
        "tickets": existing + selections, "settled": False, "provisional": False,
        "pending_ticket_statuses": statuses, "pending_ticket_reasons": reasons,
        "odds_verified": False,
        "odds_verification_note": "AI-provided selections are reproduced verbatim; GitHub does not check ESPN, markets or quotes."
    })
    write(root/"data.json", current)
    return {"status":"published", "tickets":[t["id"] for t in selections],
            "daily_stake_added": added, "bank_after_stakes": current["bank_after_stakes"]}

def main():
    try:
        result = publish()
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        result = {"status": "blocked", "reason": str(exc)[:280]}
    result["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    write("memarasix-1455-audit.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
