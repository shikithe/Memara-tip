import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from five_matches import build

class AgentFiveMatchesTests(unittest.TestCase):
    def test_five_completed_games_per_team(self):
        feed={"football_candidates":[{"sport":"football","status":"pre","league":"eng.1","home":"Home","away":"Away"}]}
        def mock(url):
            if "/summary?" in url:
                return {"header":{"ok":True},"boxscore":{"teams":[{"statistics":[{"name":"shots","displayValue":"10"}]}]}}
            day=url.split("dates=")[1][:8]
            n=int(day[-2:])
            return {"events":[{"id":day,"date":day,"status":{"type":{"state":"post"}},"competitions":[{"competitors":[{"team":{"displayName":"Home"}},{"team":{"displayName":"Away"}}]}]}]}
        result=build(feed,request=mock,days=8)
        teams=result["leagues"]["eng.1"]["teams"]
        self.assertEqual(teams["Home"]["found"],5)
        self.assertEqual(teams["Away"]["found"],5)
        self.assertTrue(teams["Home"]["complete"])
    def test_no_unrelated_leagues(self):
        result=build({"football_candidates":[]},request=lambda url: self.fail("unexpected fetch"))
        self.assertEqual(result["leagues"],{})

if __name__=="__main__":
    unittest.main()
