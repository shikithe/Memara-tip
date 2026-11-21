#!/usr/bin/env python3
"""Strict, sequential NBA ten-ticket publication gate.

The AI Scout researches each candidate and writes a dated group audit.
This deterministic program checks the entire audit and publishes *only*
the next numbered ticket. It performs no research or arbitrary picks.
"""
import argparse
import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "nba-sistem.json"
OUTPUT = ROOT / "collector-output"
FINAL = {"won", "lost", "void"}
REQUIRED_SCOUT = (
    "last_five", "season_context", "home_away_context", "h2h",
    "opponent_defense", "direct_defender", "injuries",
    "minutes_projection", "role_projection", "market", "assessment",
    "sources",
)

class GateError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise GateError(message)

def load(path):
    require(path.exists(), f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def cents(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def snapshot_path(date):
    return OUTPUT / f"nba-system-offer-{date}.json"

def audit_path(date, group):
    return OUTPUT / f"nba-system-scout-{date}-group-{group}.json"

def valid_date(date):
    require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)), "Use date YYYY-MM-DD")
    return date

def source_valid(value):
    return isinstance(value, str) and value.startswith(("https://", "http://")) and len(value) > 12

def validate_snapshot(snap, date):
    require(snap.get("date") == date, "Snapshot date mismatch")
    require(snap.get("frozen") is True and snap.get("original_snapshot_exact") is True,
            "A verified, frozen original full offer snapshot is required, not a reconstructed list")
    require(source_valid(snap.get("source")) and snap.get("captured_at_utc"),
            "Snapshot requires original source URL and acquisition timestamp")
    offers = snap.get("offers")
    require(isinstance(offers, list) and len(offers) >= 20,
            "At least 20 eligible offers needed for ten groups")
    ids = []
    for i, offer in enumerate(offers, start=1):
        require(isinstance(offer, dict), f"Offer {i} must be an object")
        require(bool(offer.get("player")), f"Offer {i}: missing player")
        # Keep the original order and a stable per-row key even when an ESPN
        # player ID is unavailable. Never manufacture ESPN IDs.
        identity = str(offer.get("player_id") or offer.get("source_position_id") or "")
        require(bool(identity) and len(identity) <= 100, f"Offer {i}: missing stable identity")
        require(offer.get("market") == "player_points", f"Offer {i}: only player points")
        require(source_valid(offer.get("source")), f"Offer {i}: missing original odds source")
        require(offer.get("bookmaker") in (snap.get("bookmaker"), None)
                and bool(snap.get("bookmaker")), f"Offer {i}: bookmaker mismatch")
        # Missing odds on individual candidates are allowed and must stay null.
        for key in ("points_line", "over_odd", "under_odd"):
            value = offer.get(key)
            if value is None:
                continue
            require(isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value), f"Offer {i}: invalid {key}")
            if key in ("over_odd", "under_odd"):
                require(1 < value < 20, f"Offer {i}: invalid {key}")
        ids.append(identity)
    require(len(ids) == len(set(ids)), "Snapshot duplicates player_id")
    n = len(offers)
    base, remainder = divmod(n, 10)
    groups = []
    offset = 0
    for k in range(1, 11):
        size = base + int(k <= remainder)
        batch = offers[offset:offset + size]
        groups.append({"number": k, "range": [offset + 1, offset + size],
                       "player_ids": [str(o.get("player_id") or o.get("source_position_id")) for o in batch],
                       "names": [o["player"] for o in batch]})
        offset += size
    if snap.get("groups"):
        require(snap["groups"] == groups, "Declared group ordering/size does not match snapshot")
    return groups

def validate_member(row, offer):
    require(isinstance(row, dict), "Each player assessment must be an object")
    identity = str(offer.get("player_id") or offer.get("source_position_id"))
    require(str(row.get("player_id")) == identity,
            "Player order/ID differs from frozen source")
    require(row.get("player") == offer.get("player"), "Player name mismatch")
    require(isinstance(row.get("rank"), int) and row["rank"] >= 1,
            "Every player needs an integer rank")
    require(isinstance(row.get("score"), (int, float))
            and math.isfinite(row["score"]), "Every player needs a finite Scout score")
    research = row.get("research")
    require(isinstance(research, dict)
            and research.get("espn_attempted") is True
            and research.get("secondary_attempted") in (True, False)
            and isinstance(research.get("coverage_note"), str)
            and len(research["coverage_note"].strip()) >= 12,
            f"{row['player']}: record first ESPN pass and evidence coverage")
    sources = row.get("sources")
    require(isinstance(sources, list) and all(source_valid(u) for u in sources),
            f"{row['player']}: invalid cited sources")
    # Every member is assessed even when data is sparse. The amount/quality of
    # verified evidence contributes to the score and uncertainty, not exclusion.
    last = row.get("last_five", [])
    require(isinstance(last, list) and len(last) <= 5,
            f"{row['player']}: last_five accepts up to five known games")
    for game in last:
        require(isinstance(game, dict) and
                all(k in game for k in ("date", "points", "minutes")),
                f"{row['player']}: only verifiable dated games")
        require(isinstance(game["points"], (int, float)) and
                isinstance(game["minutes"], (int, float)),
                f"{row['player']}: points and minutes must be numeric")
    assessment = row.get("assessment")
    require(isinstance(assessment, dict) and
            isinstance(assessment.get("reason"), str)
            and len(assessment["reason"].strip()) >= 30 and
            isinstance(assessment.get("risk"), str)
            and len(assessment["risk"].strip()) >= 15,
            f"{row['player']}: reason and uncertainty are required")
    require(assessment.get("pick") in ("over", "under"),
            f"{row['player']}: pick must be over/under")
    probability = assessment.get("estimated_probability")
    if probability is not None:
        require(isinstance(probability, (int, float)) and
                not isinstance(probability, bool) and 0 < probability < 1,
                f"{row['player']}: invalid probability estimate")
        require(bool(assessment.get("probability_method")),
                f"{row['player']}: probability method required")
    market = row.get("market")
    require(isinstance(market, dict), f"{row['player']}: market assessment required")
    for field in ("points_line", "over_odd", "under_odd"):
        require(market.get(field) == offer.get(field),
                f"{row['player']}: audited market differs from original offer")
    for key in ("h2h", "opponent_defense", "direct_defender", "injuries"):
        section = row.get(key)
        if isinstance(section, dict) and section.get("status") == "not_verified":
            require(len(str(section.get("reason", ""))) >= 15,
                    f"{row['player']}: missing {key} needs explanation")
    require(isinstance(row.get("confidence"), (int, float))
            and 0 <= row["confidence"] <= 100,
            f"{row['player']}: evidence-based confidence 0-100 required")

def validate_audit(audit, snap, groups, g):
    group = groups[g - 1]
    require(audit.get("date") == snap["date"] and audit.get("group_number") == g,
            "Audit date/group mismatch")
    require(audit.get("analysis_complete") is True, "Scout analysis not complete")
    rows = audit.get("ranking")
    require(isinstance(rows, list) and len(rows) == len(group["player_ids"]),
            f"Scout must rank ALL {len(group['player_ids'])} players")
    offers = snap["offers"][group["range"][0] - 1:group["range"][1]]
    id_to_offer = {str(x.get("player_id") or x.get("source_position_id")): x for x in offers}
    require({str(r.get("player_id")) for r in rows} == set(group["player_ids"]),
            "Audit ranking must contain exactly the original group's players")
    require(sorted(r.get("rank") for r in rows) == list(range(1, len(rows) + 1)),
            "Audit rankings must be 1..group-size, without gaps or duplication")
    for row in rows:
        validate_member(row, id_to_offer[str(row["player_id"])])
    ordered = sorted(rows, key=lambda x: x["rank"])
    require(all(ordered[i]["score"] >= ordered[i+1]["score"] for i in range(len(ordered)-1)),
            "Scout scores must be descending in rank order")
    selected = audit.get("selected_player_ids")
    require(isinstance(selected, list) and len(selected) == 2 and
            selected == [str(ordered[0]["player_id"]), str(ordered[1]["player_id"])],
            "Two selected players MUST be the actual top-ranked two")
    require(audit.get("selection_reason") and len(audit["selection_reason"]) >= 40,
            "Why the top two won must be explained")
    require(source_valid(audit.get("source_snapshot_url")),
            "Group audit missing source snapshot URL")
    picks = []
    for row in ordered[:2]:
        offer = id_to_offer[str(row["player_id"])]
        require(str(offer.get("player_id", "")).isdigit()
                and str(offer.get("espn_event_id", "")).isdigit(),
                f"{row['player']}: selected player requires verified ESPN identity/event")
        require(offer.get("start_utc"), f"{row['player']}: selected game start missing")
        require(isinstance(offer.get("points_line"), (int, float)) and
                all(isinstance(offer.get(k), (int, float)) and 1 < offer[k] < 20
                    for k in ("over_odd", "under_odd")),
                f"{row['player']}: selected player requires actual odds and line")
        require(offer.get("bookmaker") == snap.get("bookmaker"),
                f"{row['player']}: selected bookmaker must match frozen column")
        require(len(row.get("sources", [])) >= 1,
                f"{row['player']}: selected evidence source missing")
        direction = row["assessment"]["pick"]
        odd = offer["over_odd"] if direction == "over" else offer["under_odd"]
        start = datetime.fromisoformat(offer["start_utc"].replace("Z", "+00:00"))
        require(start.tzinfo is not None and start > datetime.now(timezone.utc),
                f"{row['player']}: game has started; cannot publish")
        require(row["assessment"].get("availability_confirmed") is True,
                f"{row['player']}: participation/market availability not confirmed")
        picks.append((row, offer, direction, odd))
    return picks

def next_group(cycle):
    ids = {str(t.get("id")) for t in cycle.get("tickets", [])}
    for group in range(1, 11):
        if str(group) not in ids:
            require(ids == {str(k) for k in range(1, group)},
                    "Existing tickets not a sequential prefix 1..N")
            return group
    return None

def publish(date, group=None):
    date = valid_date(date)
    ledger = load(DATA)
    cycles = ledger.setdefault("cycles", [])
    old = next((c for c in cycles if c.get("date") == date), None)
    require(not old or old.get("status") != "settled", "Cannot publish to settled cycle")
    previous = next((c for c in reversed(cycles) if c.get("date") != date), None)
    if old is None:
        require(previous is not None and previous.get("status") == "settled"
                and previous.get("accounting", {}).get("complete") is True,
                "Previous cycle must be fully settled before new cycle begins")
        bank_start = cents(previous.get("bank_end"))
    else:
        bank_start = cents(old["bank_start"])
    upcoming = next_group(old) if old else 1
    require(upcoming is not None, "All ten tickets already published")
    require(group is None or group == upcoming,
            f"Sequential gate: next ticket is {upcoming}, not {group}")
    snap = load(snapshot_path(date))
    groups = validate_snapshot(snap, date)
    audit = load(audit_path(date, upcoming))
    picks = validate_audit(audit, snap, groups, upcoming)
    used_ids = {str(l["player_id"]) for c in cycles for t in c.get("tickets", [])
                if c.get("date") == date for l in t.get("legs", [])}
    require(not any(str(offer["player_id"]) in used_ids for _, offer, _, _ in picks),
            "Player already used in this ten-ticket cycle")
    stake = cents(Decimal(str(bank_start)) * Decimal("0.01"))
    legs = []
    for row, offer, direction, odd in picks:
        legs.append({
            "player": offer["player"], "team": offer.get("team", ""),
            "opponent": offer.get("opponent", ""), "pick": direction,
            "points_line": offer["points_line"], "odd": odd,
            "bookmaker": offer["bookmaker"], "source": offer["source"],
            "espn_event_id": str(offer["espn_event_id"]),
            "player_id": str(offer["player_id"]),
            "start_utc": offer["start_utc"], "status": "pending",
            "analysis": {"last_five": row["last_five"],
                         "h2h": row["h2h"], "opponent_defense": row["opponent_defense"],
                         "direct_defender": row["direct_defender"],
                         "injuries": row["injuries"],
                         "minutes_projection": row["minutes_projection"],
                         "scout_score": row["score"],
                         "scout_note": row["assessment"]["reason"],
                         "audit": f"collector-output/nba-system-scout-{date}-group-{upcoming}.json"}
        })
    product = math.prod(l["odd"] for l in legs)
    ticket = {"id": str(upcoming), "stake": stake, "status": "pending",
              "total_odd": round(product, 4),
              "potential_payout": cents(Decimal(str(stake)) * Decimal(str(product))),
              "legs": legs}
    if old is None:
        old = {"id": f"nba-{date}", "date": date, "bank_start": bank_start,
               "status": "published", "tickets": [], "scout": {"groups_completed": []}}
        cycles.append(old)
    old["tickets"].append(ticket)
    old["status"] = "published"
    scout = old.setdefault("scout", {})
    scout["offered"] = len(snap["offers"])
    scout["total_groups"] = 10
    scout.setdefault("groups_completed", []).append(upcoming)
    scout["group_number"] = upcoming
    scout["group_range"] = "-".join(map(str, groups[upcoming - 1]["range"]))
    scout["group_selected"] = [l["player"] for l in legs]
    scout.setdefault("audit_paths", {})[str(upcoming)] = str(Path("collector-output") / audit_path(date, upcoming).name)
    scout["selection_method"] = "full_ranked_scout"
    save(DATA, ledger)
    print(json.dumps({"published_ticket": upcoming, "date": date,
                      "next_group": upcoming + 1 if upcoming < 10 else None,
                      "stake": stake, "players": [l["player"] for l in legs]},
                     ensure_ascii=False))

def status(date):
    date = valid_date(date)
    ledger = load(DATA)
    cycle = next((c for c in ledger.get("cycles", []) if c.get("date") == date), None)
    next_num = next_group(cycle) if cycle else 1
    snap = snapshot_path(date)
    print(json.dumps({"date": date, "published": len(cycle.get("tickets", [])) if cycle else 0,
                      "next_group": next_num,
                      "snapshot_exists": snap.exists(),
                      "next_audit_exists": bool(next_num and audit_path(date, next_num).exists()),
                      "workflow": "full_scout_rank_all_then_publish_next"},
                     ensure_ascii=False))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["status", "publish", "validate-snapshot"])
    p.add_argument("--date", required=True)
    p.add_argument("--group", type=int)
    args = p.parse_args()
    try:
        if args.action == "status":
            status(args.date)
        elif args.action == "validate-snapshot":
            s = load(snapshot_path(valid_date(args.date)))
            g = validate_snapshot(s, args.date)
            print(json.dumps({"date": args.date, "groups": [len(x["names"]) for x in g]}))
        else:
            publish(args.date, args.group)
    except (GateError, KeyError, TypeError, json.JSONDecodeError) as exc:
        p.exit(2, f"NBA SCOUT GATE BLOCKED: {exc}\n")

if __name__ == "__main__":
    main()
