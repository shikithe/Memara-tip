# MEMARASIX Kvoter — isolated prototype

Kvoter reads the ESPN Collector's `collector-feed.json` and an independently supplied, normalized odds file. It writes `/shared/kvoter/odds.json`. It never changes live website, bank or tickets.

**Important:** This is a containerized matching/validation engine, not yet a connected bet365 scraper or paid odds API. Without a licensed provider feed, all fixtures are marked `unavailable`; no prices are invented. Bet365 is prioritized only when it is actually present in the supplied offers.

Run tests: `cd kvoter && python -m unittest -v test_kvoter.py`

Run container: `docker compose -f kvoter/compose.yml up --build` after creating a writable output directory for container UID 65532 (for example `mkdir -p shared/kvoter && chmod 777 shared/kvoter` in the isolated test workspace) and placing `shared/collector-feed.json`. A read-only container filesystem and no network prevent unapproved data access.

Normalized provider input: `{"offers":[{"event_id":"provider-123","league":"ger.1","home":"Bayer Leverkusen","away":"VfB Stuttgart","start_utc":"2026-11-01T16:00:00Z","bookmaker":"bet365","updated_at_utc":"2026-10-31T12:00:00Z","markets":{"h2h":{"home":1.85,"draw":3.4,"away":4.2}}}]}`. Example values are illustrative only.

Matching requires exact normalized home/away names, league and kickoff within 90 minutes. Unmatched aliases are intentionally excluded rather than silently assigned incorrect prices. A provider adapter, alias map, stale-odds checks and live coverage audit are still required before production.
