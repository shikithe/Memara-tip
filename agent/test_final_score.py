import unittest
from cross_competition_history import final_score

class FinalScoreTests(unittest.TestCase):
    def test_home_away_order(self):
        event={"competitions":[{"competitors":[
            {"homeAway":"away","score":"3"},
            {"homeAway":"home","score":"2"}]}]}
        self.assertEqual(final_score(event),{"home":"2","away":"3","display":"2:3","available":True})
    def test_missing_score(self):
        event={"competitions":[{"competitors":[
            {"homeAway":"home","score":"1"},
            {"homeAway":"away"}]}]}
        self.assertFalse(final_score(event)["available"])
        self.assertIsNone(final_score(event)["display"])
    def test_nested_score(self):
        event={"competitions":[{"competitors":[
            {"homeAway":"home","score":{"displayValue":"0"}},
            {"homeAway":"away","score":{"value":2}}]}]}
        self.assertEqual(final_score(event)["display"],"0:2")

if __name__=="__main__":
    unittest.main()
