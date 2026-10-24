#!/usr/bin/env python3
"""MemaraSix numerical research layer, not a betting or prediction engine.

Uses only verified supplied inputs. Do NOT invent goals averages, player minutes,
odds or estimated win probability. No changes to published tickets/bank.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

def poisson_pmf(k, rate):
    if not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        raise ValueError("Poisson mean must be finite and positive")
    if not isinstance(k, int) or k < 0:
        raise ValueError("k must be a nonnegative integer")
    return math.exp(-rate + k * math.log(rate) - math.lgamma(k + 1))

def football_goals(home_expected, away_expected):
    """Independent Poisson baseline conditional on externally researched xG inputs."""
    total = float(home_expected) + float(away_expected)
    if not all(math.isfinite(float(x)) and 0 < float(x) <= 8 for x in (home_expected, away_expected)):
        raise ValueError("Expected goals must be finite in (0,8]")
    under_25 = sum(poisson_pmf(i, total) for i in range(3))
    home_win = draw = away_win = 0.0
    # Tail beyond 35 goals has negligible probability for rates up to 8.
    for h in range(36):
        for a in range(36):
            p = poisson_pmf(h, float(home_expected)) * poisson_pmf(a, float(away_expected))
            if h > a: home_win += p
            elif h == a: draw += p
            else: away_win += p
    return {"home_win":round(home_win,6), "draw":round(draw,6),
            "away_win":round(away_win,6), "over_2_5":round(1-under_25,6),
            "under_2_5":round(under_25,6),
            "model":"independent_poisson", "inputs":{"home_xg":float(home_expected),"away_xg":float(away_expected)},
            "limitations":"Baseline assumes independent Poisson goals; requires validated pre-match xG inputs and does not model injuries, lineups or dependence."}

def de_vig(over, under):
    """Bookmaker over/under implied probabilities, margin and proportional de-vig."""
    over, under = float(over), float(under)
    if not all(math.isfinite(x) and 1 < x <= 1000 for x in (over,under)):
        raise ValueError("Decimal odds must be above 1")
    raw_over, raw_under = 1/over, 1/under
    total = raw_over + raw_under
    return {"over_implied":round(raw_over,6), "under_implied":round(raw_under,6),
            "bookmaker_margin":round(total-1,6),
            "over_no_vig":round(raw_over/total,6), "under_no_vig":round(raw_under/total,6),
            "note":"De-vig is a market-implied benchmark, not an independent forecast."}

def edge(probability, odds):
    """Calculate theoretical ROI only with independent calibrated probability."""
    p, o = float(probability), float(odds)
    if not 0 <= p <= 1 or not math.isfinite(p) or not 1 < o <= 1000 or not math.isfinite(o):
        raise ValueError("Invalid probability or odds")
    return {"break_even_probability":round(1/o,6),"expected_roi":round(p*o-1,6)}

def analyze(feed):
    result = dict(feed)
    offers = feed.get("nba_player_points_offers", [])
    annotated = []
    for offer in offers if isinstance(offers,list) else []:
        if not isinstance(offer,dict):continue
        row = dict(offer)
        try:
            row["market_math"] = de_vig(row["over_odds"],row["under_odds"])
            row["independent_probability"] = None
            row["expected_roi"] = None
            row["math_status"] = "market_baseline_only"
        except (KeyError,TypeError,ValueError,OverflowError):
            row["market_math"] = None
            row["math_status"] = "invalid_odds"
        annotated.append(row)
    result["nba_player_points_offers"] = annotated
    result["math_layer"] = {
        "version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "nba_offers_with_market_math":sum(1 for x in annotated if x.get("math_status")=="market_baseline_only"),
        "football_probability_status":"requires_external_validated_expected_goals",
        "nba_edge_status":"requires_independent_player_points_probability_model",
        "can_publish_tickets":False,
        "notes":"No estimated probability or positive edge generated from odds alone. Football Poisson requires independently validated expected-goals inputs. These results do not overwrite A/B/C or bank."
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="collector-feed.json")
    p.add_argument("--output",default="collector-feed.json")
    a=p.parse_args()
    source=json.loads(Path(a.input).read_text(encoding="utf-8"))
    out=analyze(source)
    path=Path(a.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MEMARASIX_MATH",json.dumps(out["math_layer"]))
if __name__=="__main__":
    main()
