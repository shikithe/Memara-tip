"""Validate MemaraSix market quotes through ListaSix's approved Kvoter fixture reconciliation.

An ESPN fixture may have a different provider name.  The identity is secured by
ListaSix's league-scoped aliases and its matched_fixtures.json event IDs;
do not re-match independent strings here.
"""
from datetime import timedelta


MARKETS=(
    ("1X2","home","1"),
    ("1X2","away","2"),
    ("3+","over","3+"),
    ("2+","over","2+"),
    ("BTTS","yes","GG"),
    ("BTTS","no","NG"),
)


def verified_candidates(active, history, matched, provider, now, parse_dt, min_form=4):
    """Return real quoted candidates linked to a verified ESPN fixture and provider event."""
    if not active.get("publication_allowed"):
        return []
    by_fixture={f.get("fixture_id"):f for f in matched.get("fixtures",[])
                if f.get("fixture_id")}
    by_event={}
    for offer in provider.get("offers",[]):
        if not isinstance(offer,dict):continue
        by_event.setdefault(str(offer.get("event_id")),[]).append(offer)
    candidates=[]
    for fixture in active.get("fixtures",[]):
        fid=fixture.get("fixture_id")
        record=by_fixture.get(fid)
        if not record or fid is None:continue
        try:
            start=parse_dt(fixture["datetime"])
            if not now+timedelta(minutes=20)<start<=now+timedelta(hours=24):
                continue
            league=fid.split(":")[2]
            home,away=fixture["match"].split(" - ",1)
            if (record.get("league")!=league or record.get("home")!=home or
                    record.get("away")!=away or parse_dt(record["start_utc"])!=start):
                continue
            history_group=history.get("leagues",{}).get(league,{}).get("teams",{})
            h,a=history_group.get(home,{}),history_group.get(away,{})
            if min(h.get("found",0),a.get("found",0))<min_form:
                continue
            permitted_events={str(x) for x in record.get("provider_events",[])}
            matched_quotes={}
            for linked in record.get("odds_offers",[]):
                key=(str(linked.get("event_id")),linked.get("bookmaker"))
                matched_quotes.setdefault(key,[]).append(linked)
            if not permitted_events or not matched_quotes:
                continue
            seen=set()
            for event_id in permitted_events:
                for quote in by_event.get(event_id,[]):
                    if quote.get("league")!=league:
                        continue
                    if abs((parse_dt(quote["start_utc"])-start).total_seconds())>5400:
                        continue
                    stamped=parse_dt(quote["updated_at_utc"])
                    if not now-timedelta(hours=3)<=stamped<=now+timedelta(minutes=5):
                        continue
                    book=quote.get("bookmaker")
                    linked_quotes=matched_quotes.get((event_id,book),[])
                    if not linked_quotes or not book:
                        continue
                    for market,outcome,pick in MARKETS:
                        price=quote.get("markets",{}).get(market,{}).get(outcome)
                        if isinstance(price,bool) or not isinstance(price,(int,float)):
                            continue
                        if not 1.01<float(price)<50:
                            continue
                        # Independent cross-check: the same event, bookmaker and
                        # numeric market must exist in Kvoter's reconciled result.
                        linked_ok=any(
                            isinstance(row.get("markets",{}).get(market,{}).get(outcome),(int,float))
                            and abs(row["markets"][market][outcome]-price)<0.00001
                            for row in linked_quotes)
                        if not linked_ok:
                            continue
                        signature=(fid,event_id,book,market,outcome,round(price,5))
                        if signature in seen:
                            continue
                        seen.add(signature)
                        candidates.append({
                            "fixture_id":fid,"home":home,"away":away,"start_utc":fixture["datetime"],
                            "pick":pick,"odd":float(price),"odds":float(price),"bookmaker":book,
                            "provider_event_id":event_id,"market_source":"The Odds API",
                            "market_name":market,"odds_verified_at_utc":quote["updated_at_utc"],
                            "odds_status":"last_known_snapshot","form_home_matches":h["found"],
                            "form_away_matches":a["found"]})
        except (KeyError,ValueError,TypeError,AttributeError):
            continue
    return candidates
