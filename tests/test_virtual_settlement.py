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

    def test_cross_date_rejected(self):
        with self.assertRaises(ValueError):
            settle(sample(),{"date":"2026-10-23","source":"espn-public-unofficial","updated_at_utc":"2026-10-24T18:00:00Z","matches":[]})

    def test_unverified_cannot_settle(self):
        rows=[rec("A",0,"H1","A1","pogođen","2:1"),
              rec("A",1,"H2","A2","pogođen","2:2")]
        rows[1]["state"]="live"
        a,_=settle(sample(),scores(rows))
        self.assertEqual(a["tickets"][0]["status"],"objavljen")

if __name__=="__main__":
    unittest.main()
