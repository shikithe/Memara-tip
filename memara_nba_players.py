"""Safe optional NBA player watchlist for the MEMARA fixture collector.

Manual research candidates only. No player-game participation, bookmaker
markets, injuries, team affiliation or odds are asserted by this file.
"""
import json
from pathlib import Path

DEFAULT_WATCHLIST = Path(__file__).resolve().parent / "collector" / "nba_players_watchlist.json"


def load_nba_players(path=DEFAULT_WATCHLIST):
    """Return a separately validated roster without affecting fixture records."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = document.get("players")
    if not isinstance(rows, list):
        raise ValueError("NBA watchlist must contain a players array")
    seen_ids, seen_names, result = set(), set(), []
    for idx, record in enumerate(rows, 1):
        if not isinstance(record, dict):
            raise ValueError(f"NBA watchlist item {idx} is not an object")
        name = record.get("name")
        pid = record.get("watch_id")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"NBA watchlist item {idx} is missing name")
        if not isinstance(pid, str) or not pid.strip():
            raise ValueError(f"NBA watchlist item {idx} is missing watch_id")
        name, pid = name.strip(), pid.strip()
        if pid in seen_ids or name.casefold() in seen_names:
            raise ValueError(f"NBA watchlist contains duplicate player {name}")
        seen_ids.add(pid)
        seen_names.add(name.casefold())
        result.append({
            "watch_id": pid,
            "name": name,
            "source": "manual-watchlist",
            "availability": "unverified",
            "game_id": None,
            "points_line": None,
            "over_odds": None,
            "under_odds": None,
        })
    return result
