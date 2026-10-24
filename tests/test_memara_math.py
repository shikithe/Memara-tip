import math
import unittest
from memara_math import poisson_pmf, football_goals, de_vig, edge, analyze

class MathChecks(unittest.TestCase):
    def test_poisson(self):
        self.assertAlmostEqual(poisson_pmf(0, 2), math.exp(-2), places=10)
    def test_match_probabilities(self):
        m=football_goals(1.5, 1.2)
        self.assertAlmostEqual(m["home_win"]+m["draw"]+m["away_win"],1,places=5)
        self.assertAlmostEqual(m["over_2_5"]+m["under_2_5"],1,places=5)
    def test_de_vig(self):
        m=de_vig(1.9,1.9)
        self.assertAlmostEqual(m["over_no_vig"],.5,places=6)
        self.assertTrue(m["bookmaker_margin"]>0)
    def test_ev(self):
        self.assertAlmostEqual(edge(.5,2)["expected_roi"],0,places=6)
    def test_no_fake_edge(self):
        d=analyze({"date":"2026-10-24","football_candidates":[],"nba_player_points_offers":[{"player":"Example","over_odds":1.9,"under_odds":1.9}]})
        self.assertIsNone(d["nba_player_points_offers"][0]["independent_probability"])
        self.assertIsNone(d["nba_player_points_offers"][0]["expected_roi"])
        self.assertFalse(d["math_layer"]["can_publish_tickets"])
    def test_bad_inputs(self):
        for pair in [(1,1.9),(0,2.0),(float('nan'),2.1)]:
            with self.assertRaises(ValueError):
                de_vig(*pair)
        with self.assertRaises(ValueError):
            football_goals(-1,1)
if __name__=="__main__":unittest.main()
