# ESPN coverage audit — research only

The audit reads the 20 soccer leagues configured in production collector.py, but does not modify production code or write bankroll/tickets.

Run from repository root:

```bash
python ai-lab/espn_audit.py --date 2026-10-30 --sample 3 --output ai-lab/output/espn-audit.json
python -m unittest discover -s ai-lab -p 'test_espn_audit.py'
```

Each league is searched for up to three recently finished matches over 14 calendar days. For each, the ESPN summary is inspected for indicative presence of stats, shots, possession, lineups, and xG. Zero samples does not prove absence of data. A field being present does not guarantee quality or completeness.

**Execution status:** offline synthetic tests passed locally; live ESPN request failed because the local execution environment could not resolve ESPN DNS. Full 20-league live coverage has NOT been measured. Run in an internet-enabled GitHub Action or developer environment and review the resulting JSON. No production workflows or secrets were changed.
