"""Optional TheSportsDB free regional source for MEMARA.

Free eventsnextleague returns AT MOST ONE future event per league.
Never interpret this as a complete daily programme.
"""
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SAR = ZoneInfo("Europe/Sarajevo")
BASE = "https://www.thesportsdb.com/api/v1/json/123/eventsnextleague.php?id="
LEAGUES = {
    "Serbian Super Liga": "4671",
    "Serbian Prva Liga": "5074",
    "Bosnian Premier Liga": "4624",
    "Bosnian First League": "4911",
    "Bosnian First League of Srpska": "4912",
}


def fetch_regional(target):
    fixtures, sources, errors = [], [], []
    for league, lid in LEAGUES.items():
        url = BASE + lid
        try:
            req = Request(url, headers={"Accept": "application/json",
                                        "User-Agent": "MEMARA-Collector/1.0"})
            with urlopen(req, timeout=20) as response:
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("response too large")
            obj = json.loads(raw)
            events = obj.get("events") or []
            if not isinstance(events, list):
                raise ValueError("events is not a list")
            accepted = 0
            for event in events:
                if not isinstance(event, dict):
                    continue
                # Provider's timestamp is sometimes timezone-naive. Never
                # claim that a guessed timestamp is UTC.
                raw_ts = event.get("strTimestamp") or ""
                if not raw_ts:
                    continue
                try:
                    dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if dt.tzinfo is None:
                    # TheSportsDB documents strTimestamp as UTC without a
                    # timezone suffix. Interpret it as UTC, not Sarajevo time.
                    dt = dt.replace(tzinfo=timezone.utc)
                local = dt.astimezone(SAR)
                if local.date() != target:
                    continue
                home = (event.get("strHomeTeam") or "").strip()
                away = (event.get("strAwayTeam") or "").strip()
                if not home or not away or not event.get("idEvent"):
                    continue
                fixtures.append({
                    "id": f"sportsdb:football:{lid}:{event['idEvent']}",
                    "provider": "thesportsdb-free-limited",
                    "sport": "football", "league": league,
                    "home": home, "away": away,
                    "start_utc": dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "start_sarajevo": local.isoformat(),
                    "status": "pre" if event.get("strStatus") == "NS" else "unknown",
                    "coverage": "incomplete: free endpoint returns at most 1 next event per league",
                    "time_source": "TheSportsDB strTimestamp (naive UTC per provider documentation)",
                })
                accepted += 1
            sources.append({"provider": "thesportsdb-free-limited", "league": league,
                            "status": "ok", "count": accepted,
                            "coverage": "incomplete (one next event maximum)",
                            "source_events": len(events), "url": url})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append(f"TheSportsDB {league}: {type(exc).__name__}: {exc}")
            sources.append({"provider": "thesportsdb-free-limited", "league": league,
                            "status": "error", "count": 0, "url": url})
    return fixtures, sources, errors
