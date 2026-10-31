import unittest
from sync_nba_free import normalize_name, extract_teams, team_names

class CoverageTests(unittest.TestCase):
    def test_name_normalization(self):
        self.assertEqual(normalize_name("De'Andre Hunter"), "de'andre hunter")
    def test_offered_player_team(self):
        data={"offers":[{"player_id":"123","team":"Sacramento Kings"},{"player_id":"123","team":"Sacramento Kings"}]}
        self.assertEqual(extract_teams(data)["123"],{"sacramento kings"})
    def test_scoreboard_teams(self):
        event={"competitions":[{"competitors":[{"team":{"displayName":"Sacramento Kings"}},{"team":{"displayName":"Atlanta Hawks"}}]}]}
        self.assertIn("sacramento kings",team_names(event))

if __name__=="__main__":
    unittest.main()
