import unittest
from settle_virtual_tickets import settle

def sample():
    pub={"date":"2026-10-24","bank_before":100,"bank_after_stakes":90,
         "bank_after":90,"daily_stake":10,"settled":False,"provisional":True,
         "tickets":[
          {"id":"A","stake":6,"odds":2.25,"status":"objavljen",
           "matches":[{"home":"H1","away":"A1","pick":"1"},{"home":"H2","away":"A2","pick":"3+"}]},
          {"id":"B","stake":4,"odds":2.0,"status":"objavljen",
           "matches":[{"home":"H3","away":"A3","pick":"1"}]}]}
    return pub

def scores(records):
    return {"date":"2026-10-24","source":"espn-public-unofficial",
            "updated_at_utc":"2026-10-24T18:00:00+00:00","matches":records}
def rec(ticket,index,home,away,result,score):
    return {"ticket":ticket,"index":index,"home":home,"away":away,
            "state":"final","source":"espn-public-unofficial",
            "result_status":result,"score":score}

class TestSettlement(unittest.TestCase):
    def test_partial_only_after_last_finished(self):
        rows=[rec("A",0,"H1","A1","pogođen","2:1")]
        a,settled=settle(sample(),scores(rows))
        self.assertEqual(settled,[])
        self.assertEqual(a["bank_after"],90)
        self.assertEqual(a["tickets"][0]["status"],"objavljen")

    def test_win_and_idempotence(self):
        rows=[rec("A",0,"H1","A1","pogođen","2:1"),
              rec("A",1,"H2","A2","pogođen","2:2")]
        a,settled=settle(sample(),scores(rows))
        self.assertEqual(settled,["A"])
        self.assertEqual(a["tickets"][0]["payout"],13.5)
        self.assertEqual(a["bank_after"],103.5)
        self.assertFalse(a["settled"])
        b,again=settle(a,scores(rows))
        self.assertEqual(again,[])
        self.assertEqual(b,a)

    def test_all_finished_loss_then_net_profit(self):
        rows=[rec("A",0,"H1","A1","pogođen","2:1"),
              rec("A",1,"H2","A2","pogođen","2:2"),
              rec("B",0,"H3","A3","promašen","0:3")]
        a,settled=settle(sample(),scores(rows))
        self.assertEqual(settled,["A","B"])
        self.assertEqual(a["bank_after"],103.5)
        self.assertEqual(a["net_change"],3.5)
        self.assertTrue(a["settled"])
        self.assertEqual(a["tickets"][1]["payout"],0)

    def test_nba_void_is_winning_leg_with_one_odd_and_correct_bank(self):
        p={"date":"2026-10-24","bank_before":100,"bank_after_stakes":90,
           "bank_after":90,"daily_stake":10,"tickets":[{"id":"C","stake":10,"odds":3.5,
           "status":"objavljen","matches":[
              {"home":"TOR","away":"NYK","sport":"basketball","market":"player_points","espn_event_id":"101","player_id":"42","points_line":21.5,"pick":"over","odd":1.87},
              {"home":"POR","away":"MIN","sport":"basketball","market":"player_points","espn_event_id":"102","player_id":"43","points_line":23.5,"pick":"over","odd":1.87}]}]}
        r=[{"ticket":"C","index":0,"home":"TOR","away":"NYK","state":"final",
            "source":"espn-public-unofficial","event_id":"101","player_id":"42","sport":"basketball","player_points":24},
           {"ticket":"C","index":1,"home":"POR","away":"MIN","state":"final",
            "source":"espn-public-unofficial","event_id":"102","player_id":"43","sport":"basketball","player_points":None,
            "void":True,"void_reason":"did_not_play","result_status":"pogođen","effective_odd":1}]
        a,changed=settle(p,scores(r))
        self.assertEqual(changed,["C"])
        self.assertTrue(a["settled"])
        self.assertEqual(a["tickets"][0]["status"],"dobitan")
        self.assertEqual(a["tickets"][0]["odds"],1.87)
        self.assertEqual(a["tickets"][0]["matches"][1]["odd"],1)
        self.assertEqual(a["tickets"][0]["matches"][1]["original_odd"],1.87)
        self.assertEqual(a["tickets"][0]["matches"][1]["result_status"],"pogođen")
        self.assertEqual(a["tickets"][0]["payout"],18.7)
        self.assertEqual(a["bank_after"],108.7)
        b,again=settle(a,scores(r))
        self.assertEqual(again,[])
        self.assertEqual(b,a)

    def test_nba_void_does_not_settle_before_game_final(self):
        p={"date":"2026-10-24","bank_before":100,"bank_after_stakes":90,
           "bank_after":90,"daily_stake":10,"tickets":[{"id":"C","stake":10,"odds":1.87,
           "status":"objavljen","matches":[
              {"home":"POR","away":"MIN","sport":"basketball","market":"player_points","espn_event_id":"102","player_id":"43","points_line":23.5,"pick":"over","odd":1.87}]}]}
        r={"ticket":"C","index":0,"home":"POR","away":"MIN","state":"live",
           "source":"espn-public-unofficial","event_id":"102","player_id":"43","sport":"basketball","player_points":None,
           "void":True,"void_reason":"did_not_play"}
        a,_=settle(p,scores([r]))
        self.assertFalse(a["settled"])
        self.assertEqual(a["tickets"][0]["status"],"objavljen")
        r["state"]="final"
        b,_=settle(a,scores([r]))
        self.assertTrue(b["settled"])
        self.assertEqual(b["tickets"][0]["status"],"dobitan")

    def test_lost_nba_ticket_waits_for_every_leg_to_finish_before_archive(self):
        p={"date":"2026-10-24","bank_before":100,"bank_after_stakes":90,
           "bank_after":90,"daily_stake":10,"tickets":[{"id":"C","stake":10,"odds":3.5,
           "status":"objavljen","matches":[
              {"home":"TOR","away":"NYK","sport":"basketball","market":"player_points","espn_event_id":"101","player_id":"42","points_line":21.5,"pick":"over","odd":1.87},
              {"home":"POR","away":"MIN","sport":"basketball","market":"player_points","espn_event_id":"102","player_id":"43","points_line":23.5,"pick":"over","odd":1.87}]}]}
        loss={"ticket":"C","index":0,"home":"TOR","away":"NYK","state":"final",
              "source":"espn-public-unofficial","event_id":"101","player_id":"42","sport":"basketball","player_points":20}
        a,_=settle(p,scores([loss]))
        self.assertEqual(a["tickets"][0]["status"],"izgubljen")
        self.assertFalse(a["settled"])
        no_show={"ticket":"C","index":1,"home":"POR","away":"MIN","state":"final",
                 "source":"espn-public-unofficial","event_id":"102","player_id":"43","sport":"basketball",
                 "player_points":None,"void":True,"void_reason":"did_not_play"}
        b,_=settle(a,scores([loss,no_show]))
        self.assertTrue(b["settled"])
        self.assertEqual(b["tickets"][0]["odds"],1.87)
        self.assertEqual(b["tickets"][0]["matches"][1]["result_status"],"pogođen")
        self.assertEqual(b["tickets"][0]["payout"],0)

    def test_cross_date_rejected(self):
        with self.assertRaises(ValueError):
            settle(sample(),{"date":"2026-10-23","source":"espn-public-unofficial","updated_at_utc":"2026-10-24T18:00:00Z","matches":[]})

    def test_unverified_cannot_settle(self):
        rows=[rec("A",0,"H1","A1","pogođen","2:1"),
              rec("A",1,"H2","A2","pogođen","2:2")]
        rows[1]["state"]="live"
        a,_=settle(sample(),scores(rows))
        self.assertEqual(a["tickets"][0]["status"],"objavljen")


    def test_early_goals_credit_and_finalization(self):
        p=sample()
        p["tickets"][1]["matches"]=[{"home":"H3","away":"A3","pick":"3+"}]
        r=rec("B",0,"H3","A3","pogođen","2:1")
        r["state"]="live"
        r["event_id"]="123456"
        a,settled=settle(p,scores([r]))
        self.assertEqual(settled,["B"])
        self.assertEqual(a["tickets"][1]["status"],"dobitan")
        self.assertEqual(a["total_payout"],8.0)
        self.assertEqual(a["tickets"][1]["payout"],8.0)
        self.assertEqual(a["bank_after"],98.0)
        b,_=settle(a,scores([r]))
        self.assertEqual(a,b)
        r["state"]="final"
        c,done=settle(b,scores([r]))
        self.assertEqual(done,[])
        self.assertEqual(c["tickets"][1]["status"],"dobitan")
        self.assertEqual(c["total_payout"],8.0)
        self.assertEqual(c["bank_after"],98.0)

    def test_early_credit_reversed_on_score_correction(self):
        p=sample()
        p["tickets"][1]["matches"]=[{"home":"H3","away":"A3","pick":"3+"}]
        r=rec("B",0,"H3","A3","pogođen","2:1")
        r.update(state="live",event_id="123456")
        a,_=settle(p,scores([r]))
        r["score"]="1:1"
        b,_=settle(a,scores([r]))
        self.assertEqual(b["tickets"][1]["status"],"dobitan")
        self.assertEqual(b["bank_after"],98)

    def test_no_early_credit_for_non_goal_markets(self):
        r=rec("B",0,"H3","A3","pogođen","2:1")
        r.update(state="live",event_id="123456")
        a,_=settle(sample(),scores([r]))
        self.assertEqual(a["total_payout"],0)

if __name__=="__main__":
    unittest.main()
