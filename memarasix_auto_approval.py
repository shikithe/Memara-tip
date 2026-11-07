#!/usr/bin/env python3
"""Automatically prepare A/B approval ONLY from verified fixtures, odds and scores.

Never touches bank, tickets or archive. Published A/B remain immutable.
A/B each need true combined odds in [2,3]; B is strictly 3+ goals.
Recent scores are fetched from official ESPN finished-event scoreboards if the
ListaSix history contains score=null. Absent evidence => no approval, no guessing.
"""
import itertools
import json
import math
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from memarasix_verified_quotes import verified_candidates

BASE = "https://raw.githubusercontent.com/shikithe/Slavojka/main/"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
SAR = ZoneInfo("Europe/Sarajevo")
MIN_PRICE, MAX_PRICE = 2.00, 3.00
MAX_CALLS = 110


def dt(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timezone missing")
    return parsed.astimezone(timezone.utc)


def norm(value):
    s = unicodedata.normalize("NFKD", str(value or "").casefold().replace("ı", "i"))
    return re.sub(r"[^a-z0-9]", "", s.encode("ascii", "ignore").decode())


def source_json(url):
    req = Request(url, headers={"User-Agent": "MemaraSix-auto-A-B/1.0",
                                 "Accept": "application/json", "Cache-Control": "no-cache"})
    with urlopen(req, timeout=10) as resp:
        raw = resp.read(18_000_001)
    if len(raw) > 18_000_000:
        raise ValueError("API payload too large")
    return json.loads(raw)


def source_file(path):
    return source_json(BASE + path)


def scored(value):
    if isinstance(value, dict):
        value = value.get("value", value.get("displayValue"))
    if isinstance(value, bool) or value is None:
        return None
    if not re.fullmatch(r"\d{1,2}", str(value)):
        return None
    result = int(value)
    return result if 0 <= result <= 12 else None


def result_scores(row):
    if not isinstance(row, dict):
        return None
    a = scored(row.get("home"))
    b = scored(row.get("away"))
    return (a,b) if a is not None and b is not None else None


def official_scores(event):
    if (event.get("status") or {}).get("type", {}).get("state") != "post":
        return None
    comps = (event.get("competitions") or [])
    if not comps:
        return None
    parts = comps[0].get("competitors") or []
    if len(parts) < 2:
        return None
    scores = {c.get("homeAway"): scored(c.get("score")) for c in parts}
    if scores.get("home") is None or scores.get("away") is None:
        return None
    return (scores["home"], scores["away"])


def collect_missing_scoreboards(history, fixture_ids, getter=source_json, limit=MAX_CALLS):
    """Batch by league/date, not one network call for every historical fixture."""
    sources = {}
    needed = {}
    for fid in fixture_ids:
        parts = fid.split(":")
        if len(parts) < 4:
            continue
        league = parts[2]
        for fixture in history.get("fixtures", []):
            if fixture.get("fixture_id") != fid:
                continue
            for name in (fixture.get("home"), fixture.get("away")):
                team = history.get("leagues", {}).get(league, {}).get("teams", {}).get(name, {})
                for row in (team.get("matches") or [])[:5]:
                    if result_scores(row.get("scores")) is not None:
                        continue
                    try:
                        day = dt(row["date"]).strftime("%Y%m%d")
                        key = (league, day)
                        needed.setdefault(key, set()).add(str(row["event_id"]))
                    except (KeyError, ValueError, TypeError):
                        continue
    # Each row is an official ESPN id; never use unverified naming to attach scores.
    def task(key):
        league, day = key
        url = ESPN + league + "/scoreboard?" + urlencode({"dates": day, "limit": 500})
        doc = getter(url)
        matched = {}
        for event in doc.get("events", []):
            event_id = str(event.get("id"))
            if event_id in needed[key]:
                found = official_scores(event)
                if found is not None:
                    matched[event_id] = found
        return key, matched
    keys = sorted(needed, key=lambda k: -len(needed[k]))[:limit]
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(task, key): key for key in keys}
        for future in as_completed(futures):
            try:
                key, scores = future.result()
                for event_id, pair in scores.items():
                    sources[event_id] = (key[0], pair)
            except Exception:
                pass
    return sources, {"scoreboard_queries": len(keys), "eligible_queries": len(needed),
                     "score_ids_recovered": len(sources)}


def team_rows(history, league, team, score_lookup):
    item = history.get("leagues", {}).get(league, {}).get("teams", {}).get(team, {})
    verified = []
    seen = set()
    for row in (item.get("matches") or [])[:5]:
        eid = str(row.get("event_id") or "")
        if not eid or eid in seen:
            continue
        score = result_scores(row.get("scores"))
        if score is None:
            entry = score_lookup.get(eid)
            score = entry[1] if entry and entry[0] == row.get("competition", league) else None
        if score is None:
            continue
        pair = re.split(r"\s+at\s+", str(row.get("name") or ""), maxsplit=1, flags=re.IGNORECASE)
        if len(pair) != 2:
            continue
        away_name, home_name = map(norm, pair)
        side = "home" if norm(team) == home_name else "away" if norm(team) == away_name else None
        if side is None:
            continue
        own, against = (score if side == "home" else score[::-1])
        seen.add(eid)
        verified.append({"event_id": eid, "scored": own, "conceded": against,
                         "home": side == "home", "competition": row.get("competition"),
                         "source": "ESPN finished-event score"})
    return verified


def means(rows, venue):
    if len(rows) < 4:
        return None
    split = [x for x in rows if x["home"] == venue]
    if len(split) < 1:
        return None
    def avg(items, key):
        return sum(x[key] for x in items) / len(items)
    return {"for": .7*avg(split, "scored")+.3*avg(rows, "scored"),
            "against": .7*avg(split, "conceded")+.3*avg(rows, "conceded"),
            "games": len(rows), "venue_games": len(split)}


def model(home, away):
    # Empirical recent form is a heuristic, NOT an independently calibrated model.
    h = max(.25, min(3.8, (home["for"]+away["against"])/2))
    a = max(.25, min(3.8, (away["for"]+home["against"])/2))
    ph = [math.exp(-h)*h**n/math.factorial(n) for n in range(20)]
    pa = [math.exp(-a)*a**n/math.factorial(n) for n in range(20)]
    one = sum(ph[i]*pa[j] for i in range(20) for j in range(i))
    two = sum(ph[i]*pa[j] for i in range(20) for j in range(i+1, 20))
    t = h+a
    return {"1": one, "2": two, "2+": 1 - math.exp(-t)*(1+t),
            "3+": 1 - math.exp(-t)*(1+t+t*t/2)}


def score_quotes(candidates, history, score_lookup):
    by_fixture = {}
    for quote in candidates:
        fid = quote["fixture_id"]
        pick = quote["pick"]
        if pick not in ("1","2","2+","3+"):
            continue
        odds = float(quote["odd"])
        if not 1.08 <= odds <= 2.95:
            continue
        parts = fid.split(":")
        if len(parts) < 4:
            continue
        league = parts[2]
        key = (fid,pick)
        old = by_fixture.get(key)
        if old is None or quote["odd"] > old["odd"]:
            by_fixture[key] = quote
    computed = {}
    result = []
    for quote in by_fixture.values():
        fid = quote["fixture_id"]
        if fid not in computed:
            league = fid.split(":")[2]
            hr = team_rows(history,league,quote["home"],score_lookup)
            ar = team_rows(history,league,quote["away"],score_lookup)
            hm = means(hr, True)
            am = means(ar, False)
            computed[fid] = (model(hm,am),hr,ar) if hm and am else None
        info = computed[fid]
        if not info:
            continue
        p, home_rows, away_rows = info
        prob = p[quote["pick"]]
        price = float(quote["odd"])
        implied = 1 / price
        # A modest tolerance is allowed because the simple model is uncalibrated.
        if prob < (0.55 if quote["pick"] != "3+" else 0.51) or prob < implied - .02:
            continue
        result.append({**quote, "estimated_probability": round(prob, 5),
                       "market_implied_probability": round(implied, 5),
                       "form_home_verified": len(home_rows),
                       "form_away_verified": len(away_rows),
                       "analysis_model": "ESPN scored last-five, home/away Poisson (uncalibrated)"})
    result.sort(key=lambda q: (-q["estimated_probability"], -q["odd"], q["fixture_id"]))
    return result


def combos(options, used=None, cap=25):
    used = used or set()
    good = [q for q in options if q["fixture_id"] not in used]
    selected = []
    for count in (2,3):
        for legs in itertools.combinations(good[:cap], count):
            ids = [x["fixture_id"] for x in legs]
            if len(ids) != len(set(ids)):
                continue
            total = math.prod(x["odd"] for x in legs)
            if not MIN_PRICE - 1e-9 <= total <= MAX_PRICE + 1e-9:
                continue
            success = math.prod(x["estimated_probability"] for x in legs)
            # Rank by estimated combined pass chance, not by lowest odds alone.
            selected.append((success, -len(legs), -abs(total - 2.35), legs, total))
    selected.sort(key=lambda a: (a[0], a[1], a[2]), reverse=True)
    return selected


def build(offer, history, matched, provider, now, official_lookup=None):
    day = now.astimezone(SAR).date().isoformat()
    if offer.get("date") != day or history.get("date") != day:
        raise ValueError("Today's matching ListaSix dates required")
    if not offer.get("publication_allowed") or dt(offer["expires_at"]) <= now:
        raise ValueError("Current ListaSix offer not approved or expired")
    if not offer.get("fixtures") or not history.get("fixtures") or not history.get("leagues"):
        raise ValueError("Missing fresh matches or ESPN history")
    quotes = verified_candidates(offer, history, matched, provider, now, dt, min_form=0)
    if not quotes:
        return {"date": day, "tickets": [], "state": "no_verified_market_quotes",
                "publication_allowed": False, "quote_count": 0}
    ids = {q["fixture_id"] for q in quotes}
    scoreboard, recovered = ({}, {"scoreboard_queries":0,"score_ids_recovered":0})
    if official_lookup is not None:
        scoreboard, recovered = collect_missing_scoreboards(history, ids, official_lookup)
    ranked = score_quotes(quotes, history, scoreboard)
    b_options = [x for x in ranked if x["pick"] == "3+"]
    a_options = [x for x in ranked if x["pick"] in ("1","2","2+")]
    b_combos = combos(b_options)
    a_combos = combos(a_options)
    # Find A and B jointly without using the same fixture in both tickets.
    candidates = []
    for b in b_combos[:45]:
        used = {x["fixture_id"] for x in b[3]}
        a = next((x for x in a_combos if not any(q["fixture_id"] in used for q in x[3])), None)
        if a:
            candidates.append((a[0]*b[0], a, b))
    if candidates:
        _, ac, bc = max(candidates, key=lambda x: x[0])
    else:
        ac = a_combos[0] if a_combos else None
        bc = next((c for c in b_combos if not ac or all(x["fixture_id"] not in
                   {a["fixture_id"] for a in ac[3]} for x in c[3])), None)
    tickets = []
    for name, combination in (("A", ac),("B", bc)):
        if combination is None:
            continue
        _, _, _, legs, total = combination
        rationale = ("Automatski izbor iz potvrđenih ESPN rezultata posljednjih pet mečeva oba tima; "
                     "provjereni stvarni ESPN/kladioničarski parovi, tržište, vrijeme i kvota. "
                     "Nekalibrirani Poisson na golovima za/protiv i domaćoj/gostujućoj formi; "
                     "povrede i sastavi nisu nezavisno potvrđeni u ovom automatskom koraku. "
                     "Kvote su posljednji verifikovani API snimak i mogu se promijeniti.")
        tickets.append({"id": name,"analysis": rationale,
                        "matches": [{ "fixture_id": x["fixture_id"], "pick": x["pick"],
                                      "odd": x["odd"],"bookmaker": x["bookmaker"]}
                                    for x in legs],
                        "model_combined_probability": round(math.prod(x["estimated_probability"] for x in legs),5),
                        "combined_odds": round(total, 4)})
    report = {"date":day, "generated_at_utc":now.isoformat(),
              "selection_method":"auto_score_verified_espn_poisson_uncalibrated",
              "analysis_status":"automatic_results_based_selection",
              "state":"ready_for_publisher_validation" if tickets else "insufficient_verified_scores_or_prices",
              "tickets":tickets, "publication_allowed":bool(tickets),
              "eligible_fixture_count":len(ids),"quote_count":len(quotes),
              "modelled_market_count":len(ranked), "scoreboard_recovery":recovered,
              "warnings":["Heuristic probabilities are NOT calibrated or proven profitable.",
                          "Absences and final lineups are not independently confirmed here.",
                          "Never reuse already published tickets, skip if no verified evidence.",
                          "No bookmaker quote or model prediction guarantees a win."]}
    return report


def main():
    now = datetime.now(timezone.utc)
    today = now.astimezone(SAR).date().isoformat()
    output = Path("memarasix-1455-approved.json")
    if output.exists():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except ValueError:
            existing = {}
        if existing.get("date") == today and existing.get("tickets"):
            print("AUTO_AB_PRESERVE_EXISTING_INDEPENDENT_APPROVAL",len(existing["tickets"]))
            return 0
    try:
        offer = source_file("shared/active-list.json")
        history = source_file("shared/agent/history-h2h.json")
        provider = source_file("shared/kvoter/provider-offers.json")
        matched = source_file("shared/kvoter/matched_fixtures.json")
        result = build(offer,history,matched,provider,now,official_lookup=source_json)
    except Exception as exc:
        result = {"date":today,"tickets":[],"publication_allowed":False,
                  "state":"blocked_source_or_validation_error","reason":str(exc)[:300]}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path("collector-output").mkdir(parents=True,exist_ok=True)
    Path("collector-output/automatic-ab-analysis.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("AUTO_AB",json.dumps({k:result.get(k) for k in (
        "date","state","eligible_fixture_count","quote_count","modelled_market_count","scoreboard_recovery")},
        ensure_ascii=False))
    return 0  # fail-safe: publisher independently validates the approval


if __name__ == "__main__":
    sys.exit(main())
