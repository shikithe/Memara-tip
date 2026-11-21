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
                "second_pct":p[second],"third_pct":p["NG"],"candidate_A":True,"candidate_B":top=="3+"}
    scout = {"date":DAY,"source_active_sha256":receipt["active_sha256"],
             "source_history_sha256":canonical_hash(history),
             "total_espn_fixtures":3,"total_market_probabilities":18,
             "ranked_fixtures":[score("espn:a",p_a,"1","3+"),
                                score("espn:b",p_b,"3+","GG"),
                                score("espn:c",p_c,"3+","GG")]}
    shortlist = ["espn:b", "espn:c", "espn:a"]
    scout["detailed_ai_top_ten_fixture_ids"] = shortlist
    scout["detailed_ai_handoff"] = {
        "limit":10, "count":3, "math_recalculation_prohibited":True,
        "candidates":[{"fixture_id":fid} for fid in shortlist]}
    factor_names = ("xg_xga", "injuries_suspensions", "expected_lineups",
                    "h2h", "motivation_table", "rest_schedule", "quote_source")
    reviews = [{
        "fixture_id":fid,
        "decision":"approved" if fid in ("espn:a","espn:b") else "rejected",
        "review_summary":"Independent examination of injuries, expected lineups, xG, H2H, motivation and rest. Results used without repeating five-game Poisson math.",
        "new_factors":{name:{"status":"unavailable", "notes":"No confirmed extra data found for this fixture on this test"} for name in factor_names},
        "independent_model_check":{"status":"unavailable",
            "notes":"External model page not available for this fictional test fixture"}
    } for fid in shortlist]
    approval = {"date": DAY, "detailed_ai_review":{
        "source_active_sha256":receipt["active_sha256"],
        "source_history_sha256":scout["source_history_sha256"],
        "candidates":reviews
    },"tickets":[
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

    def test_must_review_all_top_candidates(self):
        approval,active,hist,receipt,scout=setup()
        approval["detailed_ai_review"]["candidates"].pop()
        with self.assertRaisesRegex(ValueError,"review all ten"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_shortlist_must_be_correct_ranked_order(self):
        approval,active,hist,receipt,scout=setup()
        scout["detailed_ai_handoff"]["candidates"].reverse()
        with self.assertRaisesRegex(ValueError,"TOP 10"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_no_duplicate_math_factors_in_ai_review(self):
        approval,active,hist,receipt,scout=setup()
        review=approval["detailed_ai_review"]["candidates"][0]
        review["new_factors"]["last_five_results"]={"status":"unavailable","notes":"Duplicate math"}
        with self.assertRaisesRegex(ValueError,"seven NEW factors"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_rejected_candidate_must_not_be_picked(self):
        approval,active,hist,receipt,scout=setup()
        approval["detailed_ai_review"]["candidates"][1]["decision"]="rejected"
        approval["tickets"][1]["matches"][0]={"fixture_id":"espn:c","pick":"3+","odd":1.75}
        with self.assertRaisesRegex(ValueError,"without detailed review approval"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_value_aware_market_can_differ_from_raw_probability_top(self):
        approval,active,hist,receipt,scout=setup()
        # Fixture A: 1 is the highest RAW P, but priced 3+ wins the NEW value score.
        scout["schema_version"]=2
        scout["value_selection_enabled"]=True
        values={"espn:a":{"1":40.,"3+":60.},
                "espn:b":{"2":32.,"3+":65.},
                "espn:c":{"2":30.,"3+":50.}}
        for row in scout["ranked_fixtures"]:
            fid=row["fixture_id"]
            prices={"1":active["fixtures"][0]["home_odds"],"3+":active["fixtures"][0]["over25_odds"]}
            scores=values[fid]
            row["market_value"]={k:{"score": scores.get(k), "odds":prices.get(k)}
                                for k in ("1","X","2","3+","GG","NG")}
            row["recommended_market"]="3+"
            row["recommended_pct"]=row["probability_pct"]["3+"]
            row["recommended_score"]=scores["3+"]
            row["recommended_odds"]=next(x["over25_odds"] for x in active["fixtures"] if x["fixture_id"]==fid)
        ordered=["espn:b","espn:a","espn:c"]
        scout["detailed_ai_top_ten_fixture_ids"]=ordered
        scout["detailed_ai_handoff"]["candidates"]=[{"fixture_id":x} for x in ordered]
        approval["tickets"][0]["matches"][0]["pick"]="3+"
        approval["tickets"][0]["matches"][0]["odd"]=1.6
        result=validate_scout(approval,active,hist,receipt,scout)
        self.assertTrue(result["checked"])

    def test_value_ranked_handoff_cannot_fall_back_to_raw_rank(self):
        approval,active,hist,receipt,scout=setup()
        scout["schema_version"]=2
        scout["value_selection_enabled"]=True
        for row in scout["ranked_fixtures"]:
            row["recommended_market"]=row["strongest_market"]
            row["recommended_pct"]=row["strongest_pct"]
            row["recommended_score"]=50. if row["fixture_id"]=="espn:a" else (60. if row["fixture_id"]=="espn:b" else 40.)
            row["market_value"]={k:{"score":row["recommended_score"] if k==row["recommended_market"] else None}
                                 for k in ("1","X","2","3+","GG","NG")}
        scout["detailed_ai_top_ten_fixture_ids"]=["espn:a","espn:b","espn:c"]
        with self.assertRaisesRegex(ValueError,"TOP 10"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_model_comparison_is_mandatory_for_each_candidate(self):
        approval,active,hist,receipt,scout=setup()
        del approval["detailed_ai_review"]["candidates"][0]["independent_model_check"]
        with self.assertRaisesRegex(ValueError,"independent-model check"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_model_comparison_with_verified_link_is_valid(self):
        approval,active,hist,receipt,scout=setup()
        approval["detailed_ai_review"]["candidates"][0]["independent_model_check"]={
            "status":"verified",
            "provider":"FairXG",
            "source_url":"https://fairxg.com/sport/football/match/coventry-vs-crystal-palace",
            "model_or_market_basis":"39 pct bookmakers-following; 46 pct team-news goal model",
            "notes":"Market-based probability is not independent of the bookmaker; separately report goal model."
        }
        self.assertTrue(validate_scout(approval,active,hist,receipt,scout)["checked"])

    def test_verified_factor_requires_real_public_url(self):
        approval,active,hist,receipt,scout=setup()
        approval["detailed_ai_review"]["candidates"][0]["new_factors"]["injuries_suspensions"]={
            "status":"verified","notes":"Available on official club website","source_url":""}
        with self.assertRaisesRegex(ValueError,"public source URL"):
            validate_scout(approval,active,hist,receipt,scout)

    def test_nba_only_not_checked(self):
        approval,active,hist,receipt,scout=setup()
        approval["tickets"]=[{"id":"C","matches":[{"player":"Test"}]}]
        self.assertFalse(validate_scout(approval,active,hist,receipt,scout)["checked"])

if __name__=="__main__":
    unittest.main()
