import unittest
from memara_prepare_feed import build

class NoTruncationTests(unittest.TestCase):
    def test_all_football_and_nba_preserved(self):
        football=[{"id":f"f{i}","sport":"football","league":"eng.1","status":"pre","start_utc":"2026-10-31T10:00:00Z"} for i in range(80)]
        nba=[{"id":f"n{i}","sport":"basketball","league":"nba","status":"pre","start_utc":"2026-10-31T10:00:00Z"} for i in range(22)]
        result=build({"date":"2026-10-31","fixtures":football+nba})
        self.assertEqual(len(result["football_candidates"]),80)
        self.assertEqual(len(result["nba_games"]),22)
        self.assertEqual(result["candidate_counts"]["football"],80)
        self.assertEqual(result["candidate_counts"]["nba_games"],22)
    def test_started_matches_excluded(self):
        data={"fixtures":[{"id":"f1","sport":"football","status":"in"},{"id":"f2","sport":"football","status":"pre"}]}
        result=build(data)
        self.assertEqual([f["id"] for f in result["football_candidates"]],["f2"])

if __name__=="__main__":
    unittest.main()
