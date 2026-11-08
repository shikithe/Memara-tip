import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import memarasix_ready_pr as ready


NOW=datetime(2026,11,8,16,55,tzinfo=timezone.utc)


def sample():
    active={"date":"2026-11-08", "expires_at":"2026-11-09T08:59:00+01:00",
            "publication_allowed":True,
            "fixtures":[{"fixture_id":"espn:football:bel.1:1",
                         "datetime":"2026-11-08T19:00:00Z",
                         "home_odds":1.66,"away_odds":2.05}]}
    history={"date":"2026-11-08","fixtures":[{"fixture_id":"espn:football:bel.1:1"}],
             "leagues":{"bel.1":{"teams":{}}}}
    ack={"date":"2026-11-08","active_sha256":ready.fingerprint(active),
         "fixtures":1,"synced_at_utc":"2026-11-08T15:22:11+00:00"}
    return active,history,ack


class ReadyManifestTests(unittest.TestCase):
    def checked(self, active, history, ack, now=NOW):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for name, doc in (("active-list",active),("history-h2h",history),
                              ("sync-receipt",ack)):
                folder=root/"listasix-data"
                folder.mkdir(exist_ok=True)
                (folder/(name+".json")).write_text(json.dumps(doc),encoding="utf-8")
            return ready.ready_manifest(root,now)

    def test_ready_with_verified_quotes_and_matching_hash(self):
        a,h,r=sample()
        m=self.checked(a,h,r)
        self.assertEqual(m["date"],"2026-11-08")
        self.assertEqual(m["fixtures"],1)
        self.assertEqual(m["source_active_sha256"],r["active_sha256"])
        self.assertEqual(m["status"],"WAITING_FOR_CHATGPT_AI_ANALYST")

    def test_hash_mismatch_blocks(self):
        a,h,r=sample()
        r["active_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"SHA256"):
            self.checked(a,h,r)

    def test_stale_day_blocks(self):
        a,h,r=sample()
        a["date"]="2026-11-07"
        with self.assertRaisesRegex(ValueError,"today"):
            self.checked(a,h,r)

    def test_no_market_quote_blocks(self):
        a,h,r=sample()
        del a["fixtures"][0]["home_odds"]
        del a["fixtures"][0]["away_odds"]
        r["active_sha256"]=ready.fingerprint(a)
        with self.assertRaisesRegex(ValueError,"market prices"):
            self.checked(a,h,r)

    def test_duplicate_ids_blocks(self):
        a,h,r=sample()
        a["fixtures"].append(copy.deepcopy(a["fixtures"][0]))
        r["active_sha256"]=ready.fingerprint(a)
        r["fixtures"]=2
        with self.assertRaisesRegex(ValueError,"duplicated"):
            self.checked(a,h,r)

    def test_repeated_hash_does_not_create_second_pr(self):
        a,h,r=sample()
        m=self.checked(a,h,r)
        calls=[]
        def mock_gh(method,endpoint,payload=None,optional=False):
            calls.append((method,endpoint,payload))
            if endpoint.startswith("repos/shikithe/Memara-tip/git/ref/heads/listasix-ready/"):
                return {"ref":"refs/heads/ready"}
            if "/pulls?" in endpoint:
                return [{"number":23,"state":"open"}]
            raise AssertionError("Unexpected GitHub API mutation")
        with patch.object(ready,"gh",side_effect=mock_gh):
            self.assertEqual(ready.ensure_ready_pr(m),23)
        self.assertTrue(all(method=="GET" for method,_,_ in calls))

    def test_new_hash_creates_one_pr_and_label(self):
        a,h,r=sample()
        m=self.checked(a,h,r)
        calls=[]
        def mock_gh(method,endpoint,payload=None,optional=False):
            calls.append((method,endpoint,payload))
            if method=="GET" and "/git/ref/heads/listasix-ready/" in endpoint:
                return None
            if method=="GET" and endpoint.endswith("/git/ref/heads/main"):
                return {"object":{"sha":"a"*40}}
            if method=="GET" and "/pulls?" in endpoint:
                return []
            if method=="POST" and endpoint.endswith("/pulls"):
                return {"number":28,"html_url":"https://github.com/shikithe/Memara-tip/pull/28"}
            return {"ok":True}
        with patch.object(ready,"gh",side_effect=mock_gh):
            self.assertEqual(ready.ensure_ready_pr(m),28)
        self.assertEqual(len([v for v in calls if v[0]=="POST" and v[1].endswith("/pulls")]),1)
        labels=[v for v in calls if "/issues/28/labels" in v[1]]
        self.assertEqual(labels[0][2]["labels"],["listasix-ready"])


if __name__=="__main__":
    unittest.main()
