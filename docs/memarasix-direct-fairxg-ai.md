# MemaraSix A/B — direct FairXG AI workflow (2026-11-28)

## Single daily owner
The scheduled ChatGPT A/B analyst is the ONLY selector. It opens FairXG itself. No dependency on ESPN collector, TipsterArea batch matching, GitHub TOP10_READY webhook, legacy mathematical scout, or alias feedback. Legacy feeds remain untouched for audit/backward compatibility, but are NOT prerequisites for this flow.

Schedule: 09:00 Europe/Sarajevo daily, with 10:00 and 11:00 recovery attempts only if A/B are missing. Window is [09:00, next day 09:00) in Sarajevo time. The selection run starts by checking data.json; never create a second ticket with the same letter on the same calendar day.

## Leagues, strictly
Premier League (England), La Liga (Spain), Bundesliga (Germany), Serie A (Italy), Ligue 1 (France), Serbian SuperLiga, Primeira Liga (Portugal), Eredivisie (Netherlands), Slovak Super Liga, Belgian Pro League, Ekstraklasa (Poland). No international fixtures, cups, second divisions or other countries. Query FairXG's football league filters and match pages. Serbia and Slovakia may be missing from FairXG: record explicit unavailable coverage, not invented probabilities.

## Intake, source and time validation
Read current FairXG pages directly at execution time. For each fixture in the selected leagues collect league, exact source URL, home/away, FairXG 1/X/2, over 2.5 = 3+, BTTS yes = GG, NG = 100-GG, and FairXG's *fair* odds when present. The fair odds shown by FairXG are NOT verified bookmaker prices. Verify kickoff date/time, ordered teams and competition from a reliable match schedule or the match detail; if unavailable or kickoff is <= 20 minutes away, exclude. Ensure matches are within 24 hours of 09:00 local (including tomorrow morning), not just calendar today. Never fabricate times or prices.

## AI analysis and odds
Independently review candidates: current verified squads/news/absences, rest, opponent strength, last 5–10 games (not as a rigid minimum), motivation, form and possible lineup rotation; distinguish verified from uncertain. Find contemporaneous quoted bookmaker prices from a publicly accessible offer for selected markets, with direct source URL and checked_at_utc. This lookup is direct per chosen fixture/market, not the old bulk ESPN–TipsterArea matcher. If actual odds cannot be verified, do NOT present FairXG's fair odds as betting odds or publish a priced ticket. Record clear reason.

## Ticket algorithm
B first: exactly two distinct future fixtures, market 3+ only; valid real combined quoted odds 2.00–3.00. Enumerate all eligible pairs and rank by product of FairXG 3+ probabilities, subject to independent review of risks and negative value. Tie-break by higher weaker-leg probability and stable source URL.
A second: two different fixtures (neither on B), markets 1/X/2/3+/GG/NG; real combined odds 2.00–3.00. Enumerate eligible combinations, maximize product of percentages, then weaker leg and stable source URL. Never force a wager when sources, price, match time, or risk requirements fail. A and B publish independently when complete. Do not reuse the same fixture in both tickets. Report joint probability as an approximation conditional on independence, never a calibrated guarantee.

## Minimal GitHub publisher contract
Read `shikithe/Memara-tip/data.json` and `memarasix-football-ai-approved.json`. Submit only new, researched A/B approvals (each ticket two matches) to `memarasix-football-ai-approved.json` through GitHub update_file with the latest blob SHA. Required top-level fields: date, approval_source=chatgpt_ai_analyst, publication_allowed=true, approved_at_utc, source_fingerprint, model=FairXG, tickets. Each match includes fixture_id (stable `fairxg:<urlslug>:<YYYY-MM-DD>`), home, away, league, match, datetime/start_utc ISO with timezone, pick, odd (real quoted bookmaker odds), source, quote_checked_at_utc, fairxg_source, fairxg_probability_pct, final_probability_pct, analysis. Each ticket has id, combined_odds, analysis, matches. Existing publisher decides virtual stakes and protects NBA C budget. After writing approval, read data.json again to CONFIRM publication; on no output/failure name exact blocker. No direct edits to data.json, bank, C, or archives. No duplicate publishing. Legacy TOP10 signals have no authority over this process.

## Failure behavior
No match in a particular selected league is normal. If neither A/B can be formed with validated future fixtures and actual prices, report that rather than inventing selections. On recovery run, resume only the missing ticket(s). GitHub publisher remains a single short automatic action triggered by approved-file push; no chatbot-to-GitHub webhook chain is needed.
