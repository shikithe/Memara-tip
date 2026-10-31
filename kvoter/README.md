# MEMARASIX Kvoter — isolated test branch

## Confirmed scope (31 October 2026)
1. Read `/shared/agent/history-h2h.json` produced by Agent. This contains existing historical head-to-head (H2H) statistics; Kvoter MUST NOT fetch or recalculate H2H statistics.
2. Determine leagues from the listed fixtures, and fetch Odds API prices only for events within the Collector's fixture time window. Save fetched league events to `/shared/kvoter/league-odds-raw.json` and normalized offers to `/shared/kvoter/provider-offers.json`.
3. Compare the history fixture list against the Odds API event list by league, home/away team identities and kickoff time. Produce separate lists of confirmed matches and unmatched fixtures in `/shared/kvoter/odds.json`.

## Required bookmaker markets
- 1: home win
- X: draw
- 2: away win
- 2+: over 1.5 goals
- 3+: over 2.5 goals
- BTTS: both teams to score (yes/no)

**Terminology:** The Odds API market key `h2h` means bookmaker match-winner prices (1/X/2), **not** historical head-to-head statistics. The latter already comes from Agent. The API's `totals` and `alternate_totals` can supply 2+/3+; `btts` supplies both-teams-to-score. Availability depends on provider and bookmaker; do not fabricate missing prices.

Kvoter does not publish tickets, update the bank, or perform sports-statistics analysis. Keep changes isolated until tested and approved.
