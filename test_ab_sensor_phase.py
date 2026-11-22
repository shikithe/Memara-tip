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
        self.assertEqual(phase(when(12,30)),"technical")
        self.assertEqual(phase(when(12,45)),"technical")
        self.assertEqual(phase(when(13,0)),"publication")
        self.assertEqual(phase(when(14,0)),"publication")
        self.assertEqual(phase(when(23,45)),"publication")
    def test_top10_checkpoint_suspends_preparation_only_for_same_day(self):
        ready={"date":"2026-11-23","feedback":"TOP10_CONFIRMED_WAIT_PUBLICATION"}
        self.assertEqual(phase(when(10,30),ready),"standby")
        self.assertEqual(phase(when(12,45),ready),"standby")
        self.assertEqual(phase(when(13,0),ready),"publication")
        self.assertEqual(phase(when(10,30),{"date":"2026-11-22","feedback":ready["feedback"]}),"technical")
        self.assertEqual(phase(when(10,30),{"date":ready["date"],"feedback":"TOP10_PENDING"}),"technical")

    def test_publication_feedback_stops_only_if_both_present(self):
        base={"date":"2026-11-23","both_published":False,"missing":["B"]}
        self.assertEqual(publication_feedback(base,when(14,0))["feedback"],"A_B_PUBLICATION_MISSING")
        base["both_published"]=True;base["missing"]=[]
        self.assertEqual(publication_feedback(base,when(14,15))["next_action"],"stop_today")
if __name__=="__main__":
    unittest.main()
