import unittest
from datetime import datetime, timezone, timedelta
from memara_nba_analyst import analyze

NOW = datetime(2026, 10, 29, 18, tzinfo=timezone.utc)
def iso(t): return t.isoformat()
class NBAAnalystTests(unittest.TestCase):
    def setUp(self):
        self.odds={"offers":[{"player_id":"1","player":"Example","team":"A","opponent":"B","espn_event_id":"100","start_utc":iso(NOW+timedelta(hours=8)),"last_update":iso(NOW-timedelta(hours=5)),"points_line":20.5,"over_odds":1.81,"under_odds":1.85,"bookmaker":"ExampleBook"}]}
        self.stats={"players":[{"player_id":"1","recent_games":[{"points":p,"minutes":"30:00"} for p in [20,24,22,18,26]]}]}
    def test_old_odds_are_kept_and_flagged(self):
        result=analyze(self.odds,self.stats,now=NOW)
        self.assertEqual(result["analyzed_markets"],2)
        self.assertIn("odds_need_revalidation",result["candidates"][0]["data_gaps"])
        self.assertIsNone(result["candidates"][0]["estimated_probability"])
        self.assertFalse(result["publication_allowed"])
    def test_started_game_rejected(self):
        self.odds["offers"][0]["start_utc"]=iso(NOW-timedelta(minutes=1))
        self.assertEqual(analyze(self.odds,self.stats,now=NOW)["analyzed_markets"],0)
    def test_missing_games_rejected(self):
        self.stats["players"][0]["recent_games"]=self.stats["players"][0]["recent_games"][:4]
        self.assertEqual(analyze(self.odds,self.stats,now=NOW)["analyzed_markets"],0)
    def test_verified_context_allows_uncalibrated_estimate(self):
        ctx={"1":{"source":"manual verified test","verified_at_utc":iso(NOW),"expected_minutes":30,"injury_status":"available","opponent_defense_factor":1.0,"usage_factor":1.0}}
        rows=analyze(self.odds,self.stats,ctx,now=NOW)["candidates"]
        self.assertIsNotNone(rows[0]["estimated_probability"])
        self.assertFalse(rows[0]["publication_allowed"])
if __name__=="__main__": unittest.main()
