import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from ab_sensor_phase import phase, publication_feedback
TZ=ZoneInfo("Europe/Sarajevo")
def when(h,m):
    return datetime(2026,11,23,h,m,tzinfo=TZ)
class TestPhase(unittest.TestCase):
    def test_phase_windows(self):
        self.assertEqual(phase(when(9,45)),"idle")
        self.assertEqual(phase(when(10,0)),"technical")
        self.assertEqual(phase(when(12,15)),"technical")
        self.assertEqual(phase(when(12,30)),"idle")
        self.assertEqual(phase(when(12,45)),"publication")
        self.assertEqual(phase(when(14,0)),"publication")
        self.assertEqual(phase(when(23,45)),"publication")
    def test_publication_feedback_stops_only_if_both_present(self):
        base={"date":"2026-11-23","both_published":False,"missing":["B"]}
        self.assertEqual(publication_feedback(base,when(14,0))["feedback"],"A_B_PUBLICATION_MISSING")
        base["both_published"]=True;base["missing"]=[]
        self.assertEqual(publication_feedback(base,when(14,15))["next_action"],"stop_today")
if __name__=="__main__":
    unittest.main()
