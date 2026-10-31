import unittest
from kvoter import build,match
from the_odds_api import collect

class KvoterTests(unittest.TestCase):
    def setUp(self):
        self.fixture={"fixture_id":"a","league":"ned.1","home":"Ajax Amsterdam","away":"AZ Alkmaar","start_utc":"2026-11-01T16:00:00Z"}
        self.offer={"event_id":"evt1","league":"ned.1","home":"Ajax","away":"AZ Alkmaar","start_utc":"2026-11-01T16:00:00Z","bookmaker":"example"}
    def test_alias_and_report(self):
        report=build({"fixtures":[self.fixture]},[self.offer])
        self.assertEqual((report["matched"],report["unavailable"]),(1,0))
        self.assertEqual(report["matched_fixtures"][0]["provider_events"],["evt1"])
    def test_matched_fixture_contains_correct_bookmaker_odds(self):
        offer=dict(self.offer,markets={"1X2":{"home":2.1,"draw":3.4,"away":3.2},"2+":{"over":1.35},"3+":{"over":1.95},"BTTS":{"yes":1.8,"no":2.0}})
        other=dict(offer,event_id="evt2",home="PSV",markets={"1X2":{"home":9.9}})
        report=build({"fixtures":[self.fixture]},[offer,other])
        self.assertEqual(report["matched"],1)
        self.assertEqual(report["matched_fixtures"][0]["odds_offers"],[{"event_id":"evt1","bookmaker":"example","updated_at_utc":None,"markets":offer["markets"]}])
        self.assertEqual(report["unmatched_fixtures"],[])
    def test_brighton(self):
        f=dict(self.fixture,league="eng.1",home="Brighton & Hove Albion")
        o=dict(self.offer,league="eng.1",home="Brighton")
        self.assertTrue(match(f,o))
    def test_unmatched(self):
        report=build({"fixtures":[self.fixture]},[dict(self.offer,home="PSV")])
        self.assertEqual(report["unavailable"],1)
        self.assertEqual(len(report["unmatched_fixtures"]),1)
    def test_league_window_and_all_events(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            return [{"id":"evt1","home_team":"Ajax","away_team":"AZ Alkmaar","commence_time":"2026-11-01T16:00:00Z",
                     "bookmakers":[{"key":"example","markets":[{"key":"h2h","outcomes":[{"name":"Ajax","price":1.5}]}]}]},
                    {"id":"evt2","home_team":"PSV","away_team":"Utrecht","commence_time":"2026-11-01T16:00:00Z","bookmakers":[]}]
        offers,raw,coverage,errors=collect({"fixtures":[self.fixture]},"fake",fetch=fetch)
        self.assertEqual(len(calls),1)
        self.assertIn("commenceTimeFrom=",calls[0])
        self.assertEqual(len(raw),2)
        self.assertEqual(coverage["ned.1"]["window_events"],2)
        self.assertEqual(len(offers),1)
        self.assertFalse(errors)
if __name__=="__main__": unittest.main()
