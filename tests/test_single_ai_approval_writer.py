"""Enforce a single AI approval writer; GitHub only validates/publishes."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class SingleApprovalWriterTests(unittest.TestCase):
    def test_event_sync_does_not_generate_approvals(self):
        text=(ROOT/".github/workflows/listasix-sync.yml").read_text()
        self.assertNotIn("python3 memarasix_auto_approval.py", text)
        self.assertNotIn("git add -- memarasix-1455-approved.json", text)
        self.assertNotIn("run: python3 memarasix_1455_publish.py", text)
        self.assertIn("AI_REVIEW_CAN_BEGIN_AFTER_CONFIRMED_SYNC", text)

    def test_approval_event_publisher_cannot_auto_select(self):
        text=(ROOT/".github/workflows/memarasix-scheduled-publication.yml").read_text()
        self.assertNotIn("python memarasix_auto_approval.py", text)
        self.assertNotIn("git add -- memarasix-1455-audit.json data.json memarasix-1455-approved.json", text)
        self.assertIn("python3 memarasix_1455_publish.py", text)
        self.assertIn("memarasix-1455-approved.json", text)
        self.assertNotIn("  schedule:", text)

    def test_stats_script_is_research_only(self):
        path=ROOT/"memarasix_auto_approval.py"
        text=path.read_text()
        ast.parse(text)
        self.assertNotIn('Path("memarasix-1455-approved.json")', text)
        self.assertIn('output = Path("collector-output/automatic-ab-analysis.json")', text)
        self.assertIn('result["publication_allowed"] = False', text)
        self.assertIn('result["approval_authority"] = "independent_chatgpt_ai_only"', text)

    def test_publisher_requires_independently_approved_file(self):
        text=(ROOT/"memarasix_1455_publish.py").read_text()
        self.assertIn('approval=ROOT/"memarasix-1455-approved.json"',text)
        self.assertIn('approved=load(approval)',text)
        self.assertIn('No independently reviewed A/B/C selection file',text)

if __name__=="__main__":
    unittest.main()
