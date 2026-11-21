import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nba_system_pipeline as p

DAY = "2099-01-01"

def offer(i):
    return {"player_id": str(900000 + i), "player": f"Player {i}",
            "team": "AAA", "opponent": "BBB", "espn_event_id": "12345000",
            "start_utc": "2099-01-02T02:00:00Z", "bookmaker": "DraftKings",
            "market": "player_points", "source": "https://example.com/original-odds",
            "points_line": 10.5, "over_odd": 1.9, "under_odd": 1.85}

def candidate(o, rank, score):
    return {"player_id": o["player_id"], "player": o["player"],
            "rank": rank, "score": score, "confidence": 75,
            "research": {"espn_attempted": True, "secondary_attempted": False,
                         "coverage_note": "Five ESPN game logs documented"},
            "last_five": [{"date": f"2098-12-{d:02d}", "points": 12, "minutes": 28}
                          for d in range(20,25)],
            "season_context": "12 ppg in the season",
            "home_away_context": "6 games home, 5 away",
            "h2h": {"status": "not_verified", "reason": "No confirmed head-to-head data retrieved"},
            "opponent_defense": {"status": "not_verified", "reason": "No verified defender matchup statistics"},
            "direct_defender": {"status": "not_verified", "reason": "Potential starter not publicly confirmed"},
            "injuries": {"status": "not_verified", "reason": "Latest team injury report has not been confirmed"},
            "minutes_projection": "25-30 based on last five",
            "role_projection": "rotational scorer",
            "market": {"points_line": 10.5, "over_odd": 1.9, "under_odd": 1.85},
            "assessment": {"pick": "over",
                           "estimated_probability": 0.56,
                           "probability_method": "heuristic recent results with uncertainty",
                           "availability_confirmed": True,
                           "reason": "The player's last five point totals exceed the fixed offer line.",
                           "risk": "Minutes and injury availability are not yet certain."},
            "sources": ["https://example.com/player-log"]}

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.output = self.base / "collector-output"
        self.output.mkdir()
        self.p_data = patch.object(p, "DATA", self.base / "nba-sistem.json")
        self.p_output = patch.object(p, "OUTPUT", self.output)
        self.p_data.start(); self.p_output.start()
        self.addCleanup(self.p_data.stop); self.addCleanup(self.p_output.stop)
        self.offers = [offer(i) for i in range(21)]
        self.snapshot = {
            "date": DAY, "source": "https://example.com/original-odds",
            "captured_at_utc": "2098-12-31T18:00:00Z", "frozen": True,
            "original_snapshot_exact": True, "bookmaker": "DraftKings",
            "offers": self.offers,
        }
        self.groups = p.validate_snapshot(self.snapshot, DAY)
        p.save(p.snapshot_path(DAY), self.snapshot)
        p.save(p.DATA, {"initial_bank": 1000, "cycles": [
            {"id": "nba-2098-12-31", "date": "2098-12-31",
             "status": "settled", "bank_end": 1000,
             "accounting": {"complete": True}, "tickets": [{"id": "1"}]}
        ]})

    def audit(self, group=1):
        ids = self.groups[group - 1]["player_ids"]
        offers = [next(o for o in self.offers if o["player_id"] == i) for i in ids]
        audit = {"date": DAY, "group_number": group, "analysis_complete": True,
                 "ranking": [candidate(o, i+1, 100-i) for i, o in enumerate(offers)],
                 "selected_player_ids": ids[:2],
                 "selection_reason": "The two highest-ranked offers have best estimated value relative to risk.",
                 "source_snapshot_url": "https://example.com/original-odds"}
        p.save(p.audit_path(DAY, group), audit)
        return audit

    def test_balances_ten_groups(self):
        self.assertEqual([len(g["names"]) for g in self.groups], [3] + [2]*9)
        self.assertEqual(self.groups[1]["range"], [4, 5])

    def test_requires_original_frozen_snapshot(self):
        invalid = copy.deepcopy(self.snapshot)
        invalid["original_snapshot_exact"] = False
        with self.assertRaisesRegex(p.GateError, "original or verifiably filtered"):
            p.validate_snapshot(invalid, DAY)

    def test_rejects_missing_full_ranking(self):
        audit = self.audit()
        audit["ranking"].pop()
        with self.assertRaisesRegex(p.GateError, "rank ALL"):
            p.validate_audit(audit, self.snapshot, self.groups, 1)

    def test_rejects_picking_non_top_ranked_players(self):
        audit = self.audit()
        audit["selected_player_ids"] = [self.groups[0]["player_ids"][1],
                                         self.groups[0]["player_ids"][2]]
        with self.assertRaisesRegex(p.GateError, "top-ranked"):
            p.validate_audit(audit, self.snapshot, self.groups, 1)

    def test_sparse_candidate_does_not_block_other_picks(self):
        audit = self.audit()
        sparse = audit["ranking"][-1]
        sparse["last_five"] = []
        sparse["confidence"] = 15
        sparse["research"] = {
            "espn_attempted": True, "secondary_attempted": True,
            "coverage_note": "Both sources lacked verified game-level totals"}
        picks = p.validate_audit(audit, self.snapshot, self.groups, 1)
        self.assertEqual(len(picks), 2)

    def test_selected_player_can_have_partial_games_if_real_market_verified(self):
        audit = self.audit()
        first = audit["ranking"][0]
        first["last_five"] = first["last_five"][:3]
        first["confidence"] = 50
        first["research"] = {
            "espn_attempted": True, "secondary_attempted": True,
            "coverage_note": "Only three dated games available after both sources"}
        picks = p.validate_audit(audit, self.snapshot, self.groups, 1)
        self.assertEqual(len(picks), 2)

    def test_selected_player_requires_real_odds_and_espn_identity(self):
        audit = self.audit()
        self.snapshot["offers"][0]["over_odd"] = None
        audit["ranking"][0]["market"]["over_odd"] = None
        with self.assertRaisesRegex(p.GateError, "actual odds and line"):
            p.validate_audit(audit, self.snapshot, self.groups, 1)

    def test_each_member_must_have_research_coverage(self):
        audit = self.audit()
        audit["ranking"][-1].pop("research")
        with self.assertRaisesRegex(p.GateError, "first ESPN pass"):
            p.validate_audit(audit, self.snapshot, self.groups, 1)

    def test_cannot_skip_groups(self):
        self.audit(2)
        with self.assertRaisesRegex(p.GateError, "next ticket is 1"):
            p.publish(DAY, 2)

    def test_publishes_one_group_then_requires_next_audit(self):
        self.audit()
        p.publish(DAY)
        state = p.load(p.DATA)
        cycle = state["cycles"][-1]
        self.assertEqual([t["id"] for t in cycle["tickets"]], ["1"])
        self.assertEqual(cycle["bank_start"], 1000)
        self.assertEqual(cycle["tickets"][0]["stake"], 10.0)
        with self.assertRaisesRegex(p.GateError, "Missing file"):
            p.publish(DAY)
        self.audit(2)
        p.publish(DAY)
        self.assertEqual([t["id"] for t in p.load(p.DATA)["cycles"][-1]["tickets"]],
                         ["1", "2"])

    def test_does_not_overwrite_if_audit_missing(self):
        with self.assertRaisesRegex(p.GateError, "Missing file"):
            p.publish(DAY)
        self.assertEqual(len(p.load(p.DATA)["cycles"]), 1)

if __name__ == "__main__":
    unittest.main()
