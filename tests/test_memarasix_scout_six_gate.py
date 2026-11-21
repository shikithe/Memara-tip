import copy
import unittest

from memarasix_sync_listasix import canonical_hash
from memarasix_scout_six_gate import validate_scout

DAY = "2026-11-21"

def setup():
    fields = {"date": DAY, "publication_allowed": True, "fixtures": [
        {"fixture_id": "espn:a", "match":"Home A - Away A", "home_odds": 1.7, "over25_odds":1.6},
        {"fixture_id": "espn:b", "match":"Home B - Away B", "home_odds": 1.4, "over25_odds":1.65},
        {"fixture_id": "espn:c", "match":"Home C - Away C", "home_odds": 1.8, "over25_odds":1.75},
    ]}
    history = {"date":DAY,"fixtures":[{"fixture_id":"espn:a"},{"fixture_id":"espn:b"},{"fixture_id":"espn:c"}],
               "leagues":{"eng.1":{"teams":{"Home A":{"found":5}}}}}
    receipt = {"date":DAY,"active_sha256":canonical_hash(fields)}
    p_a = {"1":60., "X":25., "2":15., "3+":55., "GG":52., "NG":48.}
    p_b = {"1":21., "X":19., "2":60., "3+":70., "GG":62., "NG":38.}
    p_c = {"1":38., "X":22., "2":40., "3+":65., "GG":57., "NG":43.}
    def score(fid,p,top,second):
        return {"fixture_id":fid,"probability_pct":p,"strongest_market":top,
                "strongest_pct":p[top],"second_market":second,
                "second_pct":p[second],"candidate_A":True,"candidate_B":top=="3+"}
    scout = {"date":DAY,"source_active_sha256":receipt["active_sha256"],
             "source_history_sha256":canonical_hash(history),
             "total_espn_fixtures":3,"total_market_probabilities":18,
             "ranked_fixtures":[score("espn:a",p_a,"1","3+"),
                                score("espn:b",p_b,"3+","GG"),
                                score("espn:c",p_c,"3+","GG")]}
    approval = {"date": DAY, "tickets":[
        {"id":"A","matches":[{"fixture_id":"espn:a","pick":"1","odd":1.7}]},
        {"id":"B","matches":[{"fixture_id":"espn:b","pick":"3+","odd":1.65}]}
    ]}
    return approval,fields,history,receipt,scout

class TestScoutSixGate(unittest.TestCase):
    def test_enforces_all_matches_and_six_markets(self):
        args = setup()
        report=validate_scout(*args)
        self.assertTrue(report["checked"])
        self.assertEqual(report["market_estimates"],18)
        self.assertEqual(report["approved_top_market_legs"],2)

    def test_weaker_pick_rejected(self):
        approval,active,hist,receipt,scout=setup()
        approval["tickets"][0]["matches"][0]["pick"]="3+"
        with self.assertRaisesRegex(ValueError,"weaker market"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_missing_one_match_blocks_shortlist(self):
        approval,active,hist,receipt,scout=setup()
        scout["ranked_fixtures"].pop()
        with self.assertRaisesRegex(ValueError,"EVERY"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_missing_one_of_six_markets_rejected(self):
        approval,active,hist,receipt,scout=setup()
        del scout["ranked_fixtures"][2]["probability_pct"]["NG"]
        with self.assertRaisesRegex(ValueError,"six markets"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_duplicate_fixture_on_a_b(self):
        approval,active,hist,receipt,scout=setup()
        approval["tickets"][1]["matches"][0]={"fixture_id":"espn:a","pick":"1","odd":1.7}
        with self.assertRaisesRegex(ValueError,"cannot appear"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_stale_source_blocks(self):
        approval,active,hist,receipt,scout=setup()
        scout["source_history_sha256"]="not-the-current-history"
        with self.assertRaisesRegex(ValueError,"synchronized history"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_nba_only_not_checked(self):
        approval,active,hist,receipt,scout=setup()
        approval["tickets"]=[{"id":"C","matches":[{"player":"Test"}]}]
        self.assertFalse(validate_scout(approval,active,hist,receipt,scout)["checked"])

if __name__=="__main__":
    unittest.main()
