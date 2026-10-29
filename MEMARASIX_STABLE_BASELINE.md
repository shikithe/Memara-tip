# MEMARASIX — STABLE BASELINE (2026-10-29)

This document records the user-approved operational baseline. It is a change-control policy, **not** GitHub branch protection. Do not alter existing production behavior as a side effect of new features.

## Main production repository
- Repository: shikithe/Memara-tip, branch: main. Keep DEMO and test branches separate.
- Main collector: `.github/workflows/memarasix-collector.yml`, `collector.py`, `memara_prepare_feed.py`.
- 20 ESPN football competitions (including eng.2, ger.2, ita.2, fra.2) plus NBA; regional best-effort feeds may also be included.
- Collector: 09:15–10:15 Europe/Sarajevo, every 5 minutes when a fresh valid feed is not already available; recovery 12:30–14:45. GitHub scheduling is best effort.
- Fixture selection: 10:00 today through 09:00 next day (exclusive), Europe/Sarajevo; only `pre` fixtures with kickoff in the future.
- Daily publication task: 13:00 Europe/Sarajevo, seven days per week, split into weekday and weekend ChatGPT automations. This schedule is managed outside this GitHub repository.
- Tickets A/B/C: independently validate; publish only verified tickets; no fabricated odds. A then B then C priority. C 'Keš kolica' total odds >=10 when available.
- Virtual bank: at most 10% daily; A/B/C 65/25/10 when all published; A/B 70/30 when C absent; other subsets retain original shares and unused budget remains in bank.
- Before publishing, archive previous date without duplication; published tickets are immutable; no double settlement. Live scores/settlement run independently from collector; do not modify the live tracking behavior unintentionally.

## Change-control requirements
1. Develop additions in a separate feature/test branch; do not edit production workflows, settlement logic, tickets, bank or archive without explicit user authorization.
2. Verify collection, fixture filtering, publishing, live scores, archival and settlement in isolation before any production merge.
3. Show a diff and test evidence before requesting approval to merge into main.
4. For genuine enforcement, configure GitHub branch protection/rulesets for `main`: require pull requests and passing checks, restrict direct pushes, prevent force pushes/deletions, and protect workflow files. A documentation file alone does not enforce these rules.
5. Keep existing scheduled ChatGPT automations at 13:00 Europe/Sarajevo unless user explicitly requests a change.
