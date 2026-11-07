# MemaraSix Scout: ListaSix -> PreScout -> Advanced Scout

Research-only change. Never edits data.json, archive.json, live-scores.json,
the virtual bank, publication logic, or existing tickets.

## Automatic chain
1. Existing "Sync ListaSix data" validates today's offer and copies
   listasix-data/active-list.json with listasix-data/analysis-brief.json.
   The full 7.8 MB history copy is unaffected.
2. After a successful sync, a separate workflow executes PreScout followed by
   Advanced Scout, with manual and retry options.
3. PreScout checks date, offer expiry, fixture ID and start (>10 minutes away).
   Using verified prior scores and venue form it independently estimates
   1/X/2, 2+, 3+, BTTS with a heuristic Poisson. Odds NEVER create probability.
4. PreScout ranks up to ten fixtures by maximum independently estimated
   probability, not by bookmaker price.
5. Advanced Scout identifies missing xG, H2H, confirmed lineups and absences,
   and assigns evidence-completeness confidence. Output goes to
   collector-output/scout-report.json.
6. This report never approves/publishes tickets. A/B/C is a separate approval.

## Observed data limitation (2026-11-07)
The compact 58-fixture ESPN brief had 580/580 prior form scores null and
just one meeting for 1/58 H2H pairs. Consequently the report has no modeled
probabilities with that source, rather than inventing confident percentages.
Upstream ESPN final-score extraction needs repair for useful Scout ranking.

## Optional independently researched evidence
File: collector-output/scout-independent-evidence.json
Use a same-date object containing fixtures keyed by exact ESPN fixture_id.
For each fixture use verified_at_utc, an xg object with home_xg_for,
home_xg_against, away_xg_for, away_xg_against and HTTPS sources; and a
team_news object with lineups_checked, absences_checked and HTTPS sources.
No example URLs or invented values should be committed as real evidence.

## Interpretation
data_confidence_score measures evidence completeness, NOT predicted win chance.
model_source labels estimates uncalibrated. estimated_ev is exploratory only.
The model must be backtested and calibrated before profitability claims.

## Tests
python -m unittest discover -s tests -p 'test_scout_pipeline.py' -v

Pull-request checks run unit tests. A feature branch is not production.
