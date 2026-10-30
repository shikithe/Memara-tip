import unittest
from kvoter import build,match,normalize_markets
class KvoterTests(unittest.TestCase):
    def setUp(self):
        self.f={"id":"espn:football:ger.1:123","sport":"football","league":"ger.1",
                "home":"Bayer Leverkusen","away":"VfB Stuttgart",
                "start_utc":"2026-11-01T16:00:00Z","start_sarajevo":"2026-11-01T17:00:00+01:00"}
        self.o={"league":"ger.1","home":"Bayer Leverkusen","away":"VfB Stuttgart",
                "start_utc":"2026-11-01T16:00:00Z","bookmaker":"bet365",
                "markets":{"h2h":{"home":1.85,"draw":3.4,"away":4.2}}}
    def test_history_h2h_input_and_markets(self):
        offer=dict(self.o,markets={"1X2":{"1":1.8,"X":3.5,"2":4.0},
                                   "over_1_5":{"over":1.3},
                                   "over_2_5":{"over":1.9},
                                   "btts":{"yes":1.75,"no":2.0}})
        history={"fixtures":[{"fixture_id":self.f["id"],**{k:v for k,v in self.f.items() if k!="id"}}]}
        result=build(history,[offer])
        self.assertEqual(result["matched"],1)
        self.assertEqual(set(result["fixtures"][0]["odds"][0]["markets"]),{"1X2","2+","3+","BTTS"})
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
