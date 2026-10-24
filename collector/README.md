# MEMARA Fixture Collector — v1

Standalone Python fixture collector. **Not** connected to the betting tickets, site publication or virtual bank.

## Where it lives
[`collector.py`](../collector.py) at the root of this repository.

## Run it locally (Python 3.10+; no extra packages)

```bash
python collector.py --date 2026-10-24 --sport all --output collector-output/fixtures.json
```

To test without network access:

```bash
python collector.py --date 2026-10-24 --offline --input collector-sample.json --output collector-output/test.json
```

Select specific football leagues:

```bash
python collector.py --date 2026-10-24 --sport football --league eng.1 --league esp.1
```

## What it does

- Reads football and basketball fixtures from selected ESPN public scoreboards and/or from a local JSON list.
- Validates key fields, converts match times to **Europe/Sarajevo** and filters by requested local calendar date.
- Deduplicates records and saves a JSON report with fixtures, per-source counts and any errors.
- Never edits `data.json`, `archive.json`, published tickets or bank.
- Runs only when explicitly executed. **No GitHub Actions has been activated.**

## What it does NOT do

- Does not cover all worldwide matches.
- Does not retrieve bookmakers' odds, injuries, xG, match predictions or betting tips.
- Does not automatically send matches to an AI model.
- Does not imply a successful request found every relevant match.

ESPN's public scoreboard access is **unofficial and best-effort**; endpoints and coverage can change. Before production deployment, switch to an appropriate licensed sports data provider and check its terms. If a source fails, the JSON reports that error and the process exits with status 2 rather than claiming complete data.

## Local JSON schema

```json
{
  "fixtures": [
    {
      "id": "external-123",
      "sport": "football",
      "league": "example",
      "home": "Example Home",
      "away": "Example Away",
      "start_utc": "2026-10-24T16:00:00Z",
      "status": "pre"
    }
  ]
}
```

Basketball uses `"sport": "basketball"`. Dates must include an explicit UTC offset.
