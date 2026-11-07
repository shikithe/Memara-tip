"""PreScout / Advanced Scout must fail closed and never change the bank."""
import unittest
from datetime import datetime, timezone
from scout_pipeline import analyze, probabilities, form_rows, verified_extra

NOW = datetime(2026, 11, 8, 9, 45, tzinfo=timezone.utc)
DATE = "2026-11-08"
ID = "espn:football:test:100"


def side(name, opponent, is_home):
    matches = []
    for i in range(5):
        venue_home = is_home if i < 3 else not is_home
        event_name = (opponent + " at " + name) if venue_home else (name + " at " + opponent)
        matches.append({
            "event_id": str(1000 + i) + name,
            "date": "2026-11-01T12:00:00Z",
            "match": event_name,
            "scores": {"home": 2 if venue_home else 1,
                       "away": 1 if venue_home else 2},
            "competition": "test.1"
        })
    return {"name": name, "last_five_matches": matches}


def offer(price=1.18):
    return {"date": DATE, "publication_allowed": True,
            "expires_at": "2026-11-09T08:59:00+01:00",
            "fixtures": [{"fixture_id": ID, "match": "Home FC - Away FC",
                          "datetime": "2026-11-08T17:00:00Z",
                          "home_odds": 1.95, "draw_odds": 3.4, "away_odds": 4.1,
                          "over15_odds": price, "over25_odds": 1.72,
                          "btts_yes_odds": 1.8}]}


def brief(scores=True):
    h, a = side("Home FC", "Other FC", True), side("Away FC", "Third FC", False)
    if not scores:
        for s in (h, a):
            for row in s["last_five_matches"]:
                row["scores"] = None
    return {"date": DATE, "fixtures": [{"fixture_id": ID,
                                        "home_form": h, "away_form": a,
                                        "head_to_head": {"found": 0, "matches": []}}]}


class ScoutTests(unittest.TestCase):
    def test_proportions_are_consistent(self):
        p = probabilities(2, 1.5)
        self.assertAlmostEqual(p["1"]+p["X"]+p["2"], 1, places=5)
        self.assertGreater(p["2+"], p["3+"])
        self.assertTrue(all(0 <= value <= 1 for value in p.values()))

    def test_verified_scores_produce_unapproved_shortlist(self):
        r = analyze(offer(), brief(), now=NOW)
        self.assertEqual(r["summary"]["modelled"], 1)
        self.assertEqual(r["summary"]["shortlisted"], 1)
        self.assertFalse(r["publication_allowed"])
        self.assertFalse(r["bank_modified"])
        self.assertFalse(r["scout_candidates"][0]["approved_for_ticket"])
        self.assertEqual(r["scout_candidates"][0]["scout_status"], "needs_advanced_scout_evidence")

    def test_null_scores_never_generate_percentages(self):
        r = analyze(offer(), brief(False), now=NOW)
        self.assertEqual(r["summary"]["modelled"], 0)
        self.assertEqual(r["summary"]["awaiting_data"], 1)
        self.assertEqual(r["pre_scout"][0]["markets"], [])

    def test_bookmaker_price_cannot_change_model_probability(self):
        a = analyze(offer(1.10), brief(), now=NOW)["pre_scout"][0]["markets"]
        b = analyze(offer(1.80), brief(), now=NOW)["pre_scout"][0]["markets"]
        prob = lambda arr: {x["type"]: x["probability"] for x in arr}
        self.assertEqual(prob(a), prob(b))

    def test_started_fixtures_not_scored(self):
        o = offer()
        o["fixtures"][0]["datetime"] = "2026-11-08T09:30:00Z"
        r = analyze(o, brief(), now=NOW)
        self.assertEqual(r["pre_scout"][0]["prescout_status"], "started_or_less_than_10min")
        self.assertEqual(r["summary"]["future"], 0)

    def test_wrong_day_rejected(self):
        o = offer()
        o["date"] = "2026-11-07"
        with self.assertRaises(ValueError):
            analyze(o, brief(), now=NOW)

    def test_ambiguous_team_identity_has_no_form(self):
        s = side("Home FC", "Other FC", True)
        s["last_five_matches"][0]["match"] = "Unrelated at Other FC"
        self.assertEqual(len(form_rows(s)), 4)

    def test_verified_external_input_requires_date_and_urls(self):
        good = {
            "verified_at_utc": "2026-11-08T08:00:00Z",
            "xg": {"sources": ["https://source.example/xg"], "home_xg_for": 1.9,
                   "home_xg_against": 1.2, "away_xg_for": 1.3, "away_xg_against": 1.6},
            "team_news": {"sources": ["https://source.example/teams"],
                          "lineups_checked": True, "absences_checked": True}
        }
        self.assertIsNotNone(verified_extra(good, NOW)["xg"])
        self.assertIsNotNone(verified_extra(good, NOW)["team_news"])
        old = dict(good, verified_at_utc="2026-11-07T08:00:00Z")
        self.assertFalse(verified_extra(old, NOW))


if __name__ == "__main__":
    unittest.main()
