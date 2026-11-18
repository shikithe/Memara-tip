import unittest
from memarasix_daily_rollover import rollover

class ArchiveHandoffTests(unittest.TestCase):
    def test_settled_ticket_moves_into_archive(self):
        old={"date":"2026-11-15","settled":True,"bank_after":228.49,
             "tickets":[{"id":"C","status":"izgubljen","matches":[{"player":"Jalen Brunson"},{"player":"Darryn Peterson"}]}]}
        fresh,history,changed=rollover(old,[],"2026-11-16")
        self.assertTrue(changed)
        self.assertEqual(fresh["tickets"],[])
        self.assertEqual(history[0]["tickets"][0]["id"],"C")
        self.assertEqual(history[0]["tickets"][0]["status"],"izgubljen")
    def test_no_archive_of_missing_nba_leg_even_if_ticket_flag_says_settled(self):
        old={"date":"2026-11-17","settled":True,"bank_after":90,
             "tickets":[{"id":"C","status":"izgubljen","matches":[
                 {"sport":"basketball","market":"player_points","result_status":"promašen"},
                 {"sport":"basketball","market":"player_points"}]}]}
        fresh,history,changed=rollover(old,[],"2026-11-18")
        self.assertFalse(changed)
        self.assertEqual(fresh,old)
        self.assertEqual(history,[])

    def test_unsettled_ticket_must_stay_visible(self):
        old={"date":"2026-11-15","settled":False,"bank_after":228.49,"tickets":[{"id":"C","status":"objavljen"}]}
        fresh,history,changed=rollover(old,[],"2026-11-16")
        self.assertFalse(changed)
        self.assertEqual(fresh,old)
        self.assertEqual(history,[])
if __name__=="__main__":unittest.main()
