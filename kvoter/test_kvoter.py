import unittest
from kvoter import build,match
class KvoterTests(unittest.TestCase):
    def setUp(self):
        self.f={"id":"espn:football:ger.1:123","sport":"football","league":"ger.1",
                "home":"Bayer Leverkusen","away":"VfB Stuttgart",
                "start_utc":"2026-11-01T16:00:00Z","start_sarajevo":"2026-11-01T17:00:00+01:00"}
        self.o={"league":"ger.1","home":"Bayer Leverkusen","away":"VfB Stuttgart",
                "start_utc":"2026-11-01T16:00:00Z","bookmaker":"bet365",
                "markets":{"h2h":{"home":1.85,"draw":3.4,"away":4.2}}}
    def test_matches(self):
        r=build({"football_candidates":[self.f]},[self.o])
        self.assertEqual(r["matched"],1)
        self.assertEqual(r["fixtures"][0]["odds"][0]["bookmaker"],"bet365")
    def test_rejects_swapped_teams(self):
        o=dict(self.o,home=self.o["away"],away=self.o["home"])
        self.assertFalse(match(self.f,o))
    def test_rejects_wrong_date(self):
        o=dict(self.o,start_utc="2026-11-02T16:00:00Z")
        self.assertFalse(match(self.f,o))
    def test_no_offers_no_fabrication(self):
        r=build({"football_candidates":[self.f]},[])
        self.assertEqual(r["unavailable"],1)
        self.assertEqual(r["fixtures"][0]["odds"],[])
if __name__=="__main__":unittest.main()
