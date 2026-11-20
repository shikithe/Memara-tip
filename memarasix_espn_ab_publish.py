#!/usr/bin/env python3
"""Technical ESPN-only publisher for independently AI-approved football A/B.
GitHub does NOT scout, select bets, or retrieve betting quotes.
"""
import json
import math
import os
import urllib.request
from datetime import datetime, timedelta, timezone
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
    today = now.astimezone(SAR).date().isoformat()
    if feed.get("date") != today or approval.get("date") != today:
        raise ValueError("today's ESPN feed and approval required")
    if utc(feed["expires_at_utc"]) <= now:
        raise ValueError("ESPN feed expired")
    if approval.get("feed_generated_at_utc") != feed.get("generated_at_utc"):
        raise ValueError("approval does not match current ESPN snapshot")
    if approval.get("approval_source") != "chatgpt_ai_analyst" or approval.get("publication_allowed") is not True:
        raise ValueError("missing independent AI publication approval")
    approved_at = utc(approval["approved_at_utc"])
    if approved_at > now + timedelta(minutes=5) or approved_at < utc(feed["generated_at_utc"]):
        raise ValueError("AI approval not after ESPN feed or is in the future")
    if approved_at.astimezone(SAR).date().isoformat() != today:
        raise ValueError("approval timestamp must be today")
    tickets = approval.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        raise ValueError("no AI-approved football tickets")
    available = {x["fixture_id"]: x for x in feed.get("football_candidates", [])}
    same_day = current.get("date") == today
    existing = current.get("tickets", []) if same_day else []
    existing_ids = {t.get("id") for t in existing}
    used = {leg.get("fixture_id") for t in existing for leg in t.get("matches", [])}
    approved_ids, chosen = set(), []
    for ticket in tickets:
        tid = ticket.get("id")
        if tid not in ("A", "B") or tid in approved_ids:
            raise ValueError("only unique football A and B tickets allowed")
        approved_ids.add(tid)
        if tid in existing_ids:
            continue  # idempotent: never republish a ticket
        if len(str(ticket.get("analysis", "")).strip()) < 40:
            raise ValueError("missing substantive AI scouting analysis")
        legs = ticket.get("matches")
        if not isinstance(legs, list) or not legs:
            raise ValueError("empty approved ticket")
        odds, verified = 1.0, []
        for leg in legs:
            fid = leg.get("fixture_id")
            if fid not in available or fid in used:
                raise ValueError("unknown/duplicate ESPN fixture")
            fixture = available[fid]
            if utc(fixture["start_utc"]) <= now + timedelta(minutes=20):
                raise ValueError("match started or begins within 20 minutes")
            pick = leg.get("pick")
            if pick not in ("1", "2", "3+", "GG", "NG"):
                raise ValueError("unknown football market")
            if tid == "B" and pick != "3+":
                raise ValueError("B requires 3+ goals")
            source = leg.get("source")
            if not isinstance(source, str) or urlparse(source).scheme != "https" or not urlparse(source).netloc:
                raise ValueError("verified HTTPS quote source required")
            if not isinstance(leg.get("bookmaker"), str) or not leg["bookmaker"].strip():
                raise ValueError("quote publisher/bookmaker must be recorded")
            quote_time = utc(leg.get("quote_checked_at_utc"))
            if quote_time > now + timedelta(minutes=2) or now - quote_time > timedelta(hours=6):
                raise ValueError("AI quote verification timestamp too old/future")
            price = float(leg["odd"])
            if not math.isfinite(price) or not 1.01 < price < 50:
                raise ValueError("invalid odds")
            odds *= price
            verified.append({
                "fixture_id": fid, "home": fixture["home"], "away": fixture["away"],
                "league": fixture["league"], "sport": "football",
                "start_utc": fixture["start_utc"], "datetime": fixture["start_utc"],
                "pick": pick, "market_name": pick, "odd": price,
                "bookmaker": leg["bookmaker"], "quote_source_url": source,
                "odds_status": "AI_verified_public_quote_not_bookmaker_confirmed",
                "quote_checked_at_utc": quote_time.isoformat()
            })
            used.add(fid)
        if not 2.0 <= odds <= 3.0:
            raise ValueError("A/B combined odds outside 2.00–3.00")
        chosen.append({"id": tid, "label": "GLAVNI TIKET" if tid == "A" else "GOLOVI",
                       "matches": verified, "odds": round(odds, 2), "analysis": ticket["analysis"]})
    return chosen

def publish(root=Path("."), now=None, feed=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(SAR).date().isoformat()
    current = read(root/"data.json")
    approval = read(root/APPROVAL)
    if feed is None:
        req = urllib.request.Request(FEED_URL, headers={"User-Agent":"MemaraSix-ESPN-Only-Publisher", "Cache-Control":"no-cache"})
        with urllib.request.urlopen(req, timeout=30) as response:
            feed = json.load(response)
    if current.get("date") != today and (current.get("date", "") > today or not current.get("settled", False)):
        raise ValueError("prior bank not settled or future-dated")
    selections = verify(approval, feed, current, now)
    if not selections:
        return {"status":"no_update", "reason":"A/B already published"}
    same_day = current.get("date") == today
    existing = list(current.get("tickets", [])) if same_day else []
    bank = float(current.get("bank_before", current.get("bank_after", 0)) if same_day else current.get("bank_after", 0))
    balance = float(current.get("bank_after", 0))
    if bank <= 0 or balance <= 0:
        raise ValueError("invalid bank")
    budget = round(bank * .1, 2)
    spent = round(sum(float(t.get("stake", 0)) for t in existing), 2)
    shares = {"A": .65, "B": .25}
    if not existing and len(selections) == 2:
        shares = {"A": .70, "B": .30}
    added = 0.
    for t in selections:
        stake = round(budget * shares[t["id"]], 2)
        if stake <= 0 or round(spent + added + stake, 2) > budget + .001 or balance < added + stake:
            raise ValueError("insufficient daily stake budget")
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
        "daily_stake": round(spent+added, 2),
        "bank_after": round(balance-added, 2),
        "bank_after_stakes": round(balance-added, 2),
        "tickets": existing + selections, "settled": False, "provisional": False,
        "pending_ticket_statuses": statuses, "pending_ticket_reasons": reasons,
        "odds_verified": False,
        "odds_verification_note": "External AI scout verified public quote and provided source; GitHub does not fetch or verify bookmaker quotes."
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
