# MEMARA A/B · Detailed AI Scout: reproducible public sources

Applies to **all ten** candidate fixtures in `Slavojka/shared/agent/scout-six-markets.json` under `detailed_ai_handoff.candidates`. No eleventh fixture; no repeats of the five-match results, goal totals, home/away rates or Poisson analysis already completed by the mathematical Scout.

The scheduled **ChatGPT A/B analyst** performs the live web investigation. GitHub cannot substitute a fixed scraper for nuanced injury news, official coach reports and new managers. This is one analyst run, not one automation per fixture.

## Source priorities and evidence

1. **Official clubs and leagues** (club news, team news, press conferences, bans) for injuries and suspensions. Search each club + date + opponent. Use the published time.
2. **Trusted independent team news** for predicted lineups and cross-checks: The Guardian, BBC Sport, Sports Mole, reputable match previews, and current specialist local media. Predicted lineups are predictions, not confirmed starting XIs.
3. **Independent probability and xG models**, when that precise fixture has a dated page: FairXG `https://fairxg.com/` and other legitimate xG providers. Compare match date, teams, competition and market. Distinguish **actual historical xG** from **forecast xG** and from **result-model expected goals**.
4. For FairXG specifically: its **published market-based bookmaker-following probability** and its **own goal-model probability after team-news allowance** are DISTINCT. Record both with correct labels when they differ. The Coventry–Crystal Palace 2026-11-21 illustration gives **39% market-based** and **46% news-adjusted goal model** for Coventry; do not merge them or present either as actual xG.
5. **Schedule, motivation and standings:** official competitions, ESPN verified data and league tables; source link + publication/verification time.
6. **H2H:** verified previous meetings only; do not invent five meetings where fewer exist.
7. **Quotes:** exact date/time, home/away, 1/X/2/3+/GG/NG, verified source URL and concrete price matching `active-list.json`. No unsupported odds.

For every one of the ten, produce seven `new_factors` keys already required by `memarasix_scout_six_gate.py`: `xg_xga`, `injuries_suspensions`, `expected_lineups`, `h2h`, `motivation_table`, `rest_schedule`, `quote_source`. Each factor must have `status: verified | unavailable` and a descriptive `notes` field; verified must include an actual `https://` public `source_url`. If data is unavailable or pages cannot be accessed, honestly mark unavailable—never fill in a guess.

Also produce **`independent_model_check`** for every reviewed candidate:
- `status: verified | unavailable`
- `notes`: what the other model says and whether it agrees with our recommended market, or why none could be verified
- if verified: `provider`, `source_url`, `model_or_market_basis` and numerical comparison where available. For a published market-following result, say this isn't independent of bookmaker odds.
- `checked_at_utc` is the time of retrieval, not the site's publication time; retain publication date separately when available.
- Never pretend a model covers a match it does not cover.

Persist the findings with `detailed_ai_review.candidates` in the future AI-approved football A/B artifact. Mark each candidate `approved`, `rejected`, or `uncertain` and write `review_summary` with concrete reasons. If a credible alternate model differs by 10 or more percentage points from our model on the SELECTED outcome, explicitly discuss the disagreement; disagreement alone is not conclusive. Where evidence is insufficient, select `uncertain` or `rejected`; never force a ticket.

The full 6-market mathematical grid and top-ten selection remain in **one and the same** existing GitHub workflow. This sources policy adds **no cron and no extra mathematical pass**. GitHub validates approval; it does not conduct this AI web research or independently know whether claims on linked pages are correct.

## Guardrails
- Football A and B have product odds 2–3 each, different ESPN fixture IDs, with B exclusively 3+ where it is the market with top composite score.
- AI must not revisit more than top ten or lower the threshold to force publication.
- No changes to already published A/B tickets, NBA C, NBA ten-ticket workflow, or banks.
- Models are estimates, not guarantees; do not claim EV or the quality index is backtest-calibrated.
