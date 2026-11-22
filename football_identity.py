"""Read football identity from the analyst's exact published selection.
No bookmaker lookup, guessing or rewriting of ticket selections.
"""
import re

def identity(match):
    if match.get("sport") == "basketball":
        return match.get("home"), match.get("away"), None, None
    fixture = str(match.get("fixture_id") or "")
    parsed = re.fullmatch(r"espn:football:([a-z0-9.]+):(\d+)", fixture)
    league, event_id = (parsed.group(1), parsed.group(2)) if parsed else (None, None)
    home, away = match.get("home"), match.get("away")
    if not home or not away:
        name = match.get("match")
        if isinstance(name, str) and name.count(" - ") == 1:
            h, a = name.split(" - ", 1)
            home, away = home or h.strip(), away or a.strip()
    return home, away, league, event_id
