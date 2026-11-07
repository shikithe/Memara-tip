import copy
import unittest
from datetime import datetime, timezone
from memarasix_auto_approval import build, official_scores, collect_missing_scoreboards, dt

NOW = datetime(2026,11,8,11,5,tzinfo=timezone.utc)
DAY = "2026-11-08"


def dataset(scoreless=False, stale=False):
    fixtures, histories, matched, offers, events = [], [], [], [], []
    leagues = {"eng.1":{"teams":{}}}
    def mk_team(label, fid_num, venue, scored, conceded):
        rows=[]
        for i in range(5):
            eventid = str(900000+fid_num*100+i*2+(0 if venue=="home" else 1))
            name = ("Opponent at "+label) if venue=="home" else (label+" at Opponent")
            row = {"event_id":eventid,"date":"2026-11-01T18:00:00Z","name":name,
                   "competition":"eng.1","scores":None if scoreless else (
                       {"home":scored,"away":conceded} if venue=="home"
                       else {"home":conceded,"away":scored})}
            rows.append(row)
            events.append({"id":eventid,"status":{"type":{"state":"post"}},
                           "competitions":[{"competitors":[{"homeAway":"home","score":scored if venue=="home" else conceded},
                                                          {"homeAway":"away","score":conceded if venue=="home" else scored}]}]})
        leagues["eng.1"]["teams"][label]={"matches":rows,"found":5}
    for n in range(6):
        ident=f"espn:football:eng.1:{40000+n}"
        home=f"Home {n}"
        away=f"Away {n}"
        if n < 2:
            home_scored, home_conceded=2,0
            away_scored, away_conceded=0,2
            pick, market, key, price = "1","1X2","home",1.50
        else:
            home_scored, home_conceded=3,2
            away_scored, away_conceded=2,3
            pick, market, key, price = "3+","3+","over",1.65
        mk_team(home,n,"home",home_scored,home_conceded)
        mk_team(away,n,"away",away_scored,away_conceded)
        start="2026-11-08T17:00:00Z"
        bookmaker="valid-book"
        eventid=f"provider-{n}"
        quote={"event_id":eventid,"league":"eng.1","home":home,"away":away,
               "start_utc":start,"bookmaker":bookmaker,"updated_at_utc":
                ("2026-11-08T03:00:00Z" if stale else "2026-11-08T11:00:00Z"),
               "markets":{market:{key:price}}}
        fixtures.append({"fixture_id":ident,"datetime":start,"match":home+" - "+away})
        histories.append({"fixture_id":ident,"league":"eng.1","home":home,"away":away})
        matched.append({"fixture_id":ident,"league":"eng.1","home":home,"away":away,
                        "start_utc":start,"provider_events":[eventid],
                        "odds_offers":[copy.deepcopy(quote)]})
        offers.append(quote)
    active={"date":DAY,"publication_allowed":True,"expires_at":"2026-11-09T08:59:00+01:00",
            "fixtures":fixtures}
    history={"date":DAY,"leagues":leagues,"fixtures":histories}
    matchdoc={"fixtures":matched}
    provider={"offers":offers}
    return active,history,matchdoc,provider,events


class AutoABTests(unittest.TestCase):
    def test_both_tickets_automatic_with_distinct_fixtures(self):
        active,history,matched,provider,_=dataset()
        output=build(active,history,matched,provider,NOW)
        self.assertEqual({t["id"] for t in output["tickets"]},{"A","B"})
        self.assertTrue(all(2 <= t["combined_odds"] <= 3 for t in output["tickets"]))
        b=next(t for t in output["tickets"] if t["id"]=="B")
        self.assertTrue(all(m["pick"]=="3+" for m in b["matches"]))
        ids=[m["fixture_id"] for t in output["tickets"] for m in t["matches"]]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(output["eligible_fixture_count"],6)

    def test_no_probability_without_real_scores(self):
        a,h,m,p,_=dataset(scoreless=True)
        report=build(a,h,m,p,NOW)
        self.assertEqual(report["tickets"],[])
        self.assertEqual(report["modelled_market_count"],0)
        self.assertFalse(report["publication_allowed"])

    def test_recover_from_official_finished_espn_scores(self):
        a,h,m,p,events=dataset(scoreless=True)
        def getter(url):
            self.assertIn("site.api.espn.com",url)
            return {"events":events}
        report=build(a,h,m,p,NOW,official_lookup=getter)
        self.assertEqual({t["id"] for t in report["tickets"]},{"A","B"})
        self.assertEqual(report["scoreboard_recovery"]["score_ids_recovered"],60)

    def test_unfinished_scores_cannot_be_used(self):
        a,h,m,p,events=dataset(scoreless=True)
        for e in events:
            e["status"]["type"]["state"]="pre"
        report=build(a,h,m,p,NOW,official_lookup=lambda u:{"events":events})
        self.assertEqual(report["tickets"],[])

    def test_stale_odds_block_all(self):
        a,h,m,p,_=dataset(stale=True)
        report=build(a,h,m,p,NOW)
        self.assertEqual(report["tickets"],[])
        self.assertEqual(report["state"],"no_verified_market_quotes")

    def test_stale_list_hard_error(self):
        a,h,m,p,_=dataset()
        a["date"]="2026-11-07"
        with self.assertRaises(ValueError):
            build(a,h,m,p,NOW)

    def test_forged_provider_event_cannot_be_approved(self):
        a,h,m,p,_=dataset()
        for row in p["offers"]:
            row["event_id"]="forged-"+row["event_id"]
        report=build(a,h,m,p,NOW)
        self.assertEqual(report["tickets"],[])

    def test_official_score_requires_post_and_two_numbers(self):
        e={"status":{"type":{"state":"post"}},"competitions":[{"competitors":[
            {"homeAway":"home","score":{"value":"2"}},
            {"homeAway":"away","score":{"displayValue":"1"}}]}]}
        self.assertEqual(official_scores(e),(2,1))
        e["status"]["type"]["state"]="pre"
        self.assertIsNone(official_scores(e))


if __name__ == "__main__":
    unittest.main()
