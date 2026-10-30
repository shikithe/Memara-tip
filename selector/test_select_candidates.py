import unittest
from selector.select_candidates import select

class SelectorTests(unittest.TestCase):
    def test_preserves_all_valid_fixtures_without_guessing(self):
        feed={"date":"2026-10-31","football_candidates":[{"id":str(i),"status":"pre","sport":"football","start_utc":"2026-10-31T12:00:00Z"} for i in range(100)],"nba_games":[{"id":"nba1","status":"pre","sport":"basketball"}]}
        result=select(feed)
        self.assertEqual(result["candidate_count"],101)
        self.assertTrue(all(not x["eligible_for_publication"] for x in result["candidates"]))
    def test_duplicate_removed(self):
        f={"id":"1","status":"pre","sport":"football"}
        result=select({"football_candidates":[f,f],"nba_games":[]})
        self.assertEqual(result["candidate_count"],1)

if __name__=="__main__":
    unittest.main()
