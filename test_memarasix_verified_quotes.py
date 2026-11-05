import unittest
from datetime import datetime, timezone
from memarasix_verified_quotes import verified_candidates

NOW=datetime(2026,11,5,11,0,tzinfo=timezone.utc)

def dt(value):
    return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(timezone.utc)

FIXTURE_ID="espn:football:uefa.europa:42"
START="2026-11-05T19:00:00Z"

def inputs():
    active={"publication_allowed":True,"fixtures":[{"fixture_id":FIXTURE_ID,
        "datetime":START,"match":"AC Milan - Ferencvaros"}]}
    history={"leagues":{"uefa.europa":{"teams":{"AC Milan":{"found":5},
        "Ferencvaros":{"found":5}}}}}
    matched={"fixtures":[{"fixture_id":FIXTURE_ID,"league":"uefa.europa",
        "home":"AC Milan","away":"Ferencvaros","start_utc":START,
        "provider_events":["e101"],
        "odds_offers":[{"event_id":"e101","bookmaker":"source",
            "markets":{"1X2":{"home":1.42},"3+":{"over":1.82}}}]}]}
    provider={"offers":[{"event_id":"e101","league":"uefa.europa",
        "home":"Milan","away":"Ferencváros","start_utc":START,
        "bookmaker":"source","updated_at_utc":"2026-11-05T10:45:00Z",
        "markets":{"1X2":{"home":1.42},"3+":{"over":1.82}}}]}
    return active,history,matched,provider

class AliasPublicationTests(unittest.TestCase):
    def test_approved_aliases_resolve_provider_event(self):
        rows=verified_candidates(*inputs(),NOW,dt)
        self.assertEqual({x["pick"] for x in rows},{"1","3+"})
        self.assertTrue(all(x["fixture_id"]==FIXTURE_ID for x in rows))
        self.assertTrue(all(x["home"]=="AC Milan" for x in rows))
        self.assertEqual({x["provider_event_id"] for x in rows},{"e101"})
    def test_wrong_event_is_rejected(self):
        a,h,m,p=inputs()
        p["offers"][0]["event_id"]="other"
        self.assertEqual(verified_candidates(a,h,m,p,NOW,dt),[])
    def test_odds_not_in_verified_kvoter_snapshot_are_rejected(self):
        a,h,m,p=inputs()
        p["offers"][0]["markets"]["3+"]["over"]=5.4
        rows=verified_candidates(a,h,m,p,NOW,dt)
        self.assertEqual([x["pick"] for x in rows],["1"])
    def test_stale_quotes_rejected(self):
        a,h,m,p=inputs()
        p["offers"][0]["updated_at_utc"]="2026-11-05T03:00:00Z"
        self.assertEqual(verified_candidates(a,h,m,p,NOW,dt),[])
    def test_incomplete_team_form_blocks_only_fixture(self):
        a,h,m,p=inputs()
        h["leagues"]["uefa.europa"]["teams"]["AC Milan"]["found"]=3
        self.assertEqual(verified_candidates(a,h,m,p,NOW,dt),[])
    def test_forged_unmatched_fixture_is_rejected(self):
        a,h,m,p=inputs()
        m["fixtures"][0]["away"]="Wrong Club"
        self.assertEqual(verified_candidates(a,h,m,p,NOW,dt),[])
    def test_independent_analysis_can_use_verified_quotes_even_if_espn_form_incomplete(self):
        a,h,m,p=inputs()
        h["leagues"]["uefa.europa"]["teams"]["AC Milan"]["found"]=0
        h["leagues"]["uefa.europa"]["teams"]["Ferencvaros"]["found"]=0
        # Low ESPN coverage is information for the analyst, not automatic
        # disqualification of real matched bookmaker odds.
        rows=verified_candidates(a,h,m,p,NOW,dt,min_form=0)
        self.assertEqual({x["pick"] for x in rows},{"1","3+"})
        self.assertTrue(all(x["form_home_matches"]==0 for x in rows))

    def test_discontinued_fixture_not_in_active_list(self):
        a,h,m,p=inputs()
        a["fixtures"]=[]
        self.assertEqual(verified_candidates(a,h,m,p,NOW,dt),[])

if __name__=="__main__":
    unittest.main()
