import unittest
from memarasix_nba_c import nba_c_rule

class NbaCTwoPlayersRuleTests(unittest.TestCase):
    def test_two_distinct_players(self):
        self.assertTrue(nba_c_rule({"id":"C","matches":[
            {"player_id":"1","market":"player_points","pick":"over"},
            {"player_id":"2","market":"player_points","pick":"under"}]}))
    def test_three_players_rejected(self):
        with self.assertRaisesRegex(ValueError,"exactly two"):
            nba_c_rule({"id":"C","matches":[
                {"player_id":str(i),"market":"player_points","pick":"over"} for i in range(3)]})
    def test_repeated_player_rejected(self):
        with self.assertRaises(ValueError):
            nba_c_rule({"id":"C","matches":[
                {"player_id":"1","market":"player_points","pick":"over"},
                {"player_id":"1","market":"player_points","pick":"under"}]})
    def test_football_pick_rejected(self):
        with self.assertRaises(ValueError):
            nba_c_rule({"id":"C","matches":[
                {"player_id":"1","market":"player_points","pick":"over"},
                {"player_id":"2","market":"football","pick":"3+"}]})
if __name__=="__main__": unittest.main()
