"""MEMARASIX: validate independently reviewed ticket selections before publication."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def validate(feed, tickets, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    if feed.get("date") != today:
        raise ValueError("Stale fixture feed")
    fixtures = {f["id"]: f for f in feed.get("football_candidates", []) + feed.get("nba_games", [])}
    used = set()
    accepted = []
    for ticket in tickets:
        legs = ticket.get("matches") or []
        if not legs:
            continue
        for leg in legs:
            eid = leg.get("fixture_id")
            fixture = fixtures.get(eid)
            if not fixture or eid in used or fixture.get("status") != "pre":
                raise ValueError("Missing, duplicate or started fixture")
            kickoff = datetime.fromisoformat(fixture["start_utc"].replace("Z", "+00:00"))
            if kickoff <= now:
                raise ValueError("Fixture already started")
            if not leg.get("bookmaker") or not leg.get("odds_verified_at_utc"):
                raise ValueError("Missing verified bookmaker quote")
            verified = datetime.fromisoformat(leg["odds_verified_at_utc"].replace("Z", "+00:00"))
            if verified.tzinfo is None or verified > now or (now-verified).total_seconds() > 3600:
                raise ValueError("Stale odds")
            if not 1.01 <= float(leg["odds"]) <= 100:
                raise ValueError("Invalid odds")
            used.add(eid)
        accepted.append(ticket)
    return accepted

def allocate(bank, available):
    budget = round(bank * 0.1, 2)
    shares = {"A":0.65,"B":0.25,"C":0.10}
    if set(available) == {"A","B"}:
        shares = {"A":0.70,"B":0.30}
    stakes = {k:round(budget*shares[k],2) for k in available}
    if sum(stakes.values()) > budget:
        last = list(stakes)[-1]
        stakes[last] = round(stakes[last]-(sum(stakes.values())-budget),2)
    return stakes
