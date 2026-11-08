"""Regression tests for approval-commit-triggered publication contract."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from memarasix_approval_gate import valid_approval, check_files
from memarasix_sync_listasix import canonical_hash

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def sample():
    a = {"date": "2026-11-08", "publication_allowed": True,
         "expires_at": "2026-11-09T08:59:00+01:00",
         "fixtures": [
             {"fixture_id": "espn:football:por.1:101", "datetime": "2026-11-08T19:00:00Z"},
             {"fixture_id": "espn:football:bel.1:102", "datetime": "2026-11-08T19:30:00Z"},
             {"fixture_id": "espn:football:fra.1:103", "datetime": "2026-11-08T20:30:00Z"},
             {"fixture_id": "espn:football:fra.1:104", "datetime": "2026-11-08T21:00:00Z"},
         ]}
    h = {"date": a["date"], "leagues": {"por.1": {"teams": {}}},
         "fixtures": [{"fixture_id": x["fixture_id"]} for x in a["fixtures"]]}
    ack = {"date": a["date"], "active_sha256": canonical_hash(a),
           "synced_at_utc": "2026-11-08T11:00:00+00:00"}
    approved = {"date": a["date"], "approval_source": "chatgpt_ai_analyst",
                "source_active_sha256": ack["active_sha256"],
                "approved_at_utc": "2026-11-08T11:40:00+00:00",
                "publication_allowed": True,
                "tickets": [{"id": "A", "analysis": "Istrazeno dovoljno izvora o domacinu i gostu; postoje rizici i neizvjesnost.",
                            "matches": [{"fixture_id": "espn:football:por.1:101",
                                         "pick": "2", "odd": 1.5, "bookmaker": "Book"},
                                        {"fixture_id": "espn:football:bel.1:102",
                                         "pick": "1", "odd": 1.6, "bookmaker": "Book"}]},
                            {"id": "B", "analysis": "Forme, izostanci i rizici su posebno analizirani; nema garancije rezultata.",
                             "matches": [{"fixture_id": "espn:football:fra.1:103",
                                          "pick": "3+", "odd": 1.5, "bookmaker": "Book"},
                                         {"fixture_id": "espn:football:fra.1:104",
                                          "pick": "3+", "odd": 1.7, "bookmaker": "Book"}]}]}
    return a, h, ack, approved


class EventApprovalTests(unittest.TestCase):
    def test_approval_at_any_hour_after_sync(self):
        a, h, ack, approved = sample()
        result = valid_approval(a, h, ack, approved, NOW)
        self.assertEqual(result["tickets"], ["A", "B"])
        self.assertEqual(result["source_active_sha256"], canonical_hash(a))

    def test_no_ai_approval_means_no_publication(self):
        a, h, ack, approved = sample()
        approved["tickets"] = []
        with self.assertRaises(ValueError):
            valid_approval(a,h,ack,approved,NOW)

    def test_approval_before_receipt_must_be_rejected(self):
        a, h, ack, approved = sample()
        approved["approved_at_utc"] = "2026-11-08T10:59:00Z"
        with self.assertRaises(ValueError):
            valid_approval(a,h,ack,approved,NOW)

    def test_old_hash_requires_new_ai_analysis(self):
        a, h, ack, approved = sample()
        a["fixtures"].append({"fixture_id": "new", "datetime": "2026-11-08T19:45:00Z"})
        with self.assertRaises(ValueError):
            valid_approval(a,h,ack,approved,NOW)

    def test_approval_without_chatgpt_authority_rejected(self):
        a, h, ack, approved = sample()
        approved["approval_source"] = "github_auto_approval"
        with self.assertRaises(ValueError):
            valid_approval(a,h,ack,approved,NOW)

    def test_no_approval_from_future(self):
        a,h,ack,approved=sample()
        approved["approved_at_utc"] = "2026-11-08T13:00:00Z"
        with self.assertRaises(ValueError):
            valid_approval(a,h,ack,approved,NOW)

    def test_reject_started_fixture_even_when_approved(self):
        a,h,ack,approved=sample()
        a["fixtures"][0]["datetime"] = "2026-11-08T12:10:00Z"
        ack["active_sha256"] = canonical_hash(a)
        approved["source_active_sha256"] = ack["active_sha256"]
        with self.assertRaises(ValueError):
            valid_approval(a,h,ack,approved,NOW)

    def test_b_must_be_3plus(self):
        a,h,ack,approved=sample()
        approved["tickets"][1]["matches"][0]["pick"] = "2+"
        with self.assertRaises(ValueError):
            valid_approval(a,h,ack,approved,NOW)

    def test_duplicate_fixture_not_allowed(self):
        a,h,ack,approved=sample()
        approved["tickets"][1]["matches"][0]["fixture_id"] = "espn:football:bel.1:102"
        with self.assertRaises(ValueError):
            valid_approval(a,h,ack,approved,NOW)

    def test_approval_file_must_exist(self):
        a,h,ack,approved=sample()
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)
            for name,data in (("listasix-data/active-list.json",a),
                              ("listasix-data/history-h2h.json",h),
                              ("listasix-data/sync-receipt.json",ack)):
                p=path/name
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaises(ValueError):
                check_files(path,NOW)


if __name__ == "__main__":
    unittest.main()
