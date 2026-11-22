import unittest
from inspektor_ab import inspect

TODAY = "2026-11-22"

def state():
    site = {"date": TODAY, "tickets": []}
    feed = {"date": TODAY, "generated_at_utc": "2026-11-22T08:45:00Z",
            "football_candidates": [{"fixture_id": "espn:1", "home": "Alpha",
                                     "away": "Beta", "start_utc": "2026-11-22T15:00:00Z"}]}
    active = {"date": TODAY, "fixtures": [{"fixture_id": "espn:1",
              "match": "Alpha - Beta", "datetime": "2026-11-22T15:00:00Z",
              "home_odds": 1.8}]}
    scout = {"date": TODAY, "source_feed_generated_at_utc": feed["generated_at_utc"],
             "all_fixtures_evaluated": 1}
    history = {"date": TODAY, "fixtures": [{"fixture_id": "espn:1"}]}
    return site, feed, active, scout, history

class InspectorTests(unittest.TestCase):
    def test_missing_scout_does_not_restart_espn_or_odds(self):
        s, f, a, c, h = state()
        c["date"] = "2026-11-21"
        self.assertEqual(inspect(s, f, a, c, TODAY, h)["next_stage"], "scout_6of6")

    def test_scout_exists_require_analyst(self):
        s, f, a, c, h = state()
        self.assertEqual(inspect(s, f, a, c, TODAY, h)["next_stage"], "ai_analysis")

    def test_both_tickets_stop(self):
        s, f, a, c, h = state()
        s["tickets"] = [{"id": x, "status": "objavljen", "matches": [{"pick": "GG"}]}
                        for x in ("A", "B")]
        self.assertEqual(inspect(s, f, a, c, TODAY, h)["next_stage"], "complete")

    def test_missing_espn(self):
        s, f, a, c, h = state()
        self.assertEqual(inspect(s, None, a, c, TODAY, h)["next_stage"], "espn")

    def test_stale_history_routes_to_history_before_scout(self):
        s, f, a, c, h = state()
        h["date"] = "2026-11-21"
        self.assertEqual(inspect(s, f, a, c, TODAY, h)["next_stage"], "history")

    def test_missing_quotes_do_not_block_scout(self):
        s, f, a, c, h = state()
        a["fixtures"][0]["home_odds"] = None
        c["date"] = "2026-11-21"
        r = inspect(s, f, a, c, TODAY, h)
        self.assertEqual(r["next_stage"], "scout_6of6")
        self.assertTrue(r["ai_quote_recovery_needed"])

    def test_missing_one_ticket_not_complete(self):
        s, f, a, c, h = state()
        s["tickets"] = [{"id": "A", "status": "objavljen", "matches": [{"pick": "GG"}]}]
        self.assertEqual(inspect(s, f, a, c, TODAY, h)["next_stage"], "ai_analysis")

if __name__ == "__main__":
    unittest.main()
