import unittest
from inspektor_ab import inspect as raw_inspect

def inspect(site, feed, active, scout, today, history=None, top10=None, odds_feedback=None):
    """Default to consistent finalized odds for existing inspector fixtures."""
    if odds_feedback is None and isinstance(feed, dict) and isinstance(active, dict):
        rows=active.get("fixtures", [])
        quoted=sum(any(isinstance(x.get(k),(int,float)) and 1.01 < x[k] < 50 for k in ("home_odds","draw_odds","away_odds","over25_odds","btts_yes_odds","btts_no_odds")) for x in rows)
        odds_feedback={"date":today,"feedback":"ODDS_READY","status":"ready_for_scout",
                       "final":True,"espn_total":len(feed.get("football_candidates", [])),
                       "matched_with_quotes":quoted,"skipped_unmatched":len(rows)-quoted}
    return raw_inspect(site,feed,active,scout,today,history,top10,odds_feedback)

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

    def test_confirmed_top10_halts_technical_checks(self):
        s, f, a, c, h = state()
        c["detailed_ai_handoff"] = {"count":1,"candidates":[{"fixture_id":"espn:1"}]}
        top10 = {"date":TODAY,"feedback":"TOP10_READY","source_fingerprint":"a"*64,
                 "count":1,"fixture_ids":["espn:1"],"candidates":[{"fixture_id":"espn:1"}]}
        result=inspect(s,f,a,c,TODAY,h,top10)
        self.assertEqual(result["next_stage"],"await_publication")
        self.assertEqual(result["feedback"],"TOP10_CONFIRMED_WAIT_PUBLICATION")
        top10["date"]="2026-11-21"
        self.assertEqual(inspect(s,f,a,c,TODAY,h,top10)["next_stage"],"ai_analysis")

    def test_missing_final_odds_feedback_blocks_downstream(self):
        s, f, a, c, h = state()
        result = raw_inspect(s, f, a, c, TODAY, h, None, None)
        self.assertEqual(result["next_stage"], "tipsterarea")
        self.assertIn("ODDS_READY", result["reason"])
        invalid={"date":TODAY,"feedback":"ODDS_READY","status":"ready_for_scout",
                 "final":True,"espn_total":1,"matched_with_quotes":0,"skipped_unmatched":1}
        self.assertEqual(raw_inspect(s,f,a,c,TODAY,h,None,invalid)["next_stage"],"tipsterarea")

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
