import unittest
from check_ab_publication import check

class ABCheckTests(unittest.TestCase):
    def test_both_published(self):
        sample={"date":"2026-11-22","tickets":[
            {"id":"A","status":"objavljen","matches":[{"pick":"1"}]},
            {"id":"B","status":"objavljen","matches":[{"pick":"GG"}]}]}
        result=check(sample,"2026-11-22")
        self.assertTrue(result["both_published"])
        self.assertEqual(result["missing"], [])

    def test_missing_b(self):
        sample={"date":"2026-11-22","tickets":[{"id":"A","status":"objavljen","matches":[{"pick":"1"}]}]}
        self.assertEqual(check(sample,"2026-11-22")["missing"], ["B"])

    def test_approval_without_site_entry_not_published(self):
        sample={"date":"2026-11-22","tickets":[
            {"id":"A","status":"approved","matches":[{"pick":"1"}]},
            {"id":"B","status":"objavljen","matches":[]}]}
        self.assertEqual(check(sample,"2026-11-22")["missing"], ["A","B"])

    def test_yesterdays_tickets_not_today(self):
        sample={"date":"2026-11-21","tickets":[
            {"id":"A","status":"objavljen","matches":[{}]},
            {"id":"B","status":"objavljen","matches":[{}]}]}
        self.assertFalse(check(sample,"2026-11-22")["both_published"])

if __name__=="__main__":
    unittest.main()
