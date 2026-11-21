#!/usr/bin/env python3
"""Partition a verified daily BetSharp NBA snapshot into ten stable ordered JSON lists."""
import json
from pathlib import Path

SOURCE = Path("collector-output/betsharp-nba-daily.json")

def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    date = data.get("game_date_et")
    offers = data.get("offers")
    if data.get("status") != "ok" or not date or not isinstance(offers, list) or len(offers) < 10:
        raise ValueError("A dated, successful BetSharp snapshot with at least ten offers is required")
    if data.get("player_count") != len(offers):
        raise ValueError("BetSharp snapshot player count mismatch")
    if any(o.get("game_date_et") != date or not o.get("points_market") for o in offers):
        raise ValueError("Invalid game date or missing points offer")
    root = Path("collector-output/nba-system-lists") / date
    root.mkdir(parents=True, exist_ok=True)
    base, remainder = divmod(len(offers), 10)
    offset = 0
    for number in range(1, 11):
        size = base + (number <= remainder)
        batch = [{**o, "original_offer_position": offset + i + 1}
                 for i, o in enumerate(offers[offset:offset + size])]
        document = {
            "date": date, "list_number": number, "total_lists": 10,
            "source": "BetSharp", "source_url": data["source_url"],
            "source_snapshot": str(SOURCE), "captured_at_utc": data.get("collected_at_utc"),
            "total_offers": len(offers), "group_size": size,
            "original_positions": [offset + 1, offset + size],
            "status": "awaiting_scout", "analysis_complete": False,
            "publication_allowed": False, "offers": batch,
        }
        (root / f"list-{number:02d}.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        offset += size
    if offset != len(offers):
        raise ValueError("Partition did not cover entire source offer")
    print(f"BetSharp {date}: {len(offers)} offers divided into 10 lists; "
          f"base {base}, remainder {remainder}")

if __name__ == "__main__":
    main()
