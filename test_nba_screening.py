import unittest
from nba_screening import analyze

class OddsLineTests(unittest.TestCase):
    def test_balanced_market_only_and_unique_player(self):
        stats={"generated_at_utc":"now","players":[{"player_id":"1","weighted_avg_points":24,"avg_minutes":31,"complete_five":True,"preseason_count":0,"regular_count":5,"recent_games":[{"points":20},{"points":24},{"points":25},{"points":23},{"points":28}]}]}
        base={"player_id":"1","player":"Test Player","points_line":21.5,"over_odds":1.86,"under_odds":1.88,"bookmaker":"Book A"}
        offers={"generated_at_utc":"snapshot","offers":[dict(base),dict(base,over_odds=1.40,under_odds=2.7),dict(base,bookmaker="Book B")]}
        report=analyze(offers,stats)
        self.assertEqual(report["review_count"],1)
        self.assertEqual(report["eligible_market_offers"],2)
        self.assertEqual(report["review_candidates"][0]["odds"],1.86)
        self.assertFalse(report["publication_allowed"])
    def test_lower_bound_included(self):
        stats={"generated_at_utc":"now","players":[{"player_id":"2","weighted_avg_points":20,"avg_minutes":30,"complete_five":True,"preseason_count":0,"regular_count":5,"recent_games":[{"points":20}]*5}]}
        offers={"generated_at_utc":"today","offers":[{"player_id":"2","player":"Test","points_line":18.5,"over_odds":1.75,"under_odds":1.90}]}
        self.assertEqual(analyze(offers,stats)["review_count"],1)

    def test_no_force_fill(self):
        report=analyze({"generated_at_utc":"snapshot","offers":[]},{"generated_at_utc":"now","players":[]})
        self.assertEqual(report["review_count"],0)

if __name__=="__main__":unittest.main()
