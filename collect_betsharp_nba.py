#!/usr/bin/env python3
"""Fetch BetSharp NBA player points, filtered by actual NBA game date (US ET).
Read-only input. Never creates tickets, predictions, or invented offers.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

URL = "https://betsharp.com/nba/props?m=points"
BOOKS = ("DK", "FD", "MGM", "BR", "KAL")

def american_to_decimal(value):
    if value is None:
        return None
    value = int(value)
    return round(1 + (value / 100 if value > 0 else 100 / abs(value)), 4)

def parse_book(cell):
    txt = cell.get_text(" ", strip=True)
    m = re.search(r"(\d+(?:\.\d+)?)\s*o\s*([+-]\d+)\s*u\s*([+-]\d+)", txt, flags=re.I)
    if not m:
        return None
    line, over, under = float(m.group(1)), int(m.group(2)), int(m.group(3))
    return {"line": line, "over_american": over, "under_american": under,
            "over_decimal": american_to_decimal(over), "under_decimal": american_to_decimal(under)}

def parse_html(html, target_date):
    soup = BeautifulSoup(html, "html.parser")
    offers = []
    for tr in soup.select("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 8:
            continue
        player_link = tds[0].select_one('a[href*="/nba/player/"]')
        game_link = tds[1].select_one('a[href*="/nba/game/"]')
        if not player_link or not game_link:
            continue
        href = game_link.get("href", "")
        match = re.search(r"/nba/game/(\d{4}-\d{2}-\d{2})-", href)
        if not match or match.group(1) != target_date:
            continue
        name = player_link.get_text(" ", strip=True)
        team = tds[0].get_text(" ", strip=True).replace(name, "", 1).strip()
        game = game_link.get_text(" ", strip=True)
        time_et = tds[1].get_text(" ", strip=True).replace(game, "", 1).strip()
        # Page has best over/under and one column per provider.
        provider_cells = dict(zip(BOOKS, tds[4:9]))
        books = {book: quote for book, cell in provider_cells.items()
                 if (quote := parse_book(cell)) is not None}
        if not books:
            continue
        offers.append({"player": name, "team": team, "game": game,
                       "game_date_et": match.group(1), "game_time_et": time_et,
                       "player_url": "https://betsharp.com" + player_link.get("href", ""),
                       "game_url": "https://betsharp.com" + href,
                       "points_market": books})
    uniq = {(o["player"], o["game"], o["game_date_et"]): o for o in offers}
    return sorted(uniq.values(), key=lambda x: (x["game"], x["player"]))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="NBA game date America/New_York, YYYY-MM-DD")
    p.add_argument("--output", default="collector-output/betsharp-nba-daily.json")
    a = p.parse_args()
    day = a.date or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    req = Request(URL, headers={"User-Agent": "Mozilla/5.0 (compatible; MemaraSixScout/1.0)",
                                 "Accept": "text/html"})
    with urlopen(req, timeout=35) as response:
        html = response.read(4 * 1024 * 1024 + 1).decode("utf-8")
    if len(html) > 4 * 1024 * 1024:
        raise ValueError("BetSharp response too large")
    offers = parse_html(html, day)
    if not offers:
        raise RuntimeError("No verified BetSharp points rows for game date " + day + "; existing file preserved")
    data = {"schema_version": "1.0", "source": "BetSharp",
            "source_url": URL, "market": "player_points",
            "game_date_et": day, "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "player_count": len(offers), "status": "ok",
            "note": "Market snapshot only; player participation and odds require re-verification.",
            "offers": offers}
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BetSharp NBA", day, "players:", len(offers), "saved to", path)

if __name__ == "__main__":
    main()
