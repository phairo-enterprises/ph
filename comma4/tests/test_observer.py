import importlib.util
import json
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "openpilot/tools/max_observer/observer.py"
spec = importlib.util.spec_from_file_location("max_observer", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def source(points):
    return ("\\n".join(json.dumps(p, sort_keys=True) for p in points) + "\\n").encode()

class ObserverTests(unittest.TestCase):
    def test_cardinals_and_diagonals(self):
        vectors = [(10,0),(0,10),(-10,0),(0,-10),(10,10),(-10,10),(-10,-10),(10,-10)]
        self.assertEqual([m.key_for_displacement(*v, deadzone=0) for v in vectors],
                         ["D", "W", "A", "S", "E", "Q", "Z", "C"])

    def test_static(self):
        raw = source([{"tick":0,"entities":[{"track_id":"a","x_m":0,"y_m":0}]},
                      {"tick":1,"entities":[{"track_id":"a","x_m":0,"y_m":0}]}])
        self.assertEqual(m.replay(raw)["events"][0]["inferred_key"], "NONE")

    def test_exact_replay(self):
        raw = source([{"tick":0,"entities":[{"track_id":"a","x_m":0,"y_m":0}]},
                      {"tick":3,"entities":[{"track_id":"a","x_m":1,"y_m":0}]}])
        self.assertEqual(m.replay(raw), m.replay(raw))
        self.assertEqual(m.replay(raw)["events"][0]["dt_ticks"], 3)
        self.assertEqual(m.replay(raw)["events"][0]["inferred_key"], "D")

    def test_quantization_ties_half_even(self):
        self.assertEqual(m.quantized_mm("0.005"), 0)
        self.assertEqual(m.quantized_mm("0.015"), 2)

    def test_multiple_tracks(self):
        raw = source([{"tick":0,"entities":[{"track_id":"a","x_m":0,"y_m":0},
                                             {"track_id":"b","x_m":0,"y_m":0}]},
                      {"tick":1,"entities":[{"track_id":"a","x_m":1,"y_m":0},
                                             {"track_id":"b","x_m":0,"y_m":1}]}])
        self.assertEqual([e["inferred_key"] for e in m.replay(raw)["events"]], ["D", "W"])

    def test_duplicate_track_rejected(self):
        raw = source([{"tick":0,"entities":[{"track_id":"a","x_m":0,"y_m":0},
                                             {"track_id":"a","x_m":1,"y_m":0}]}])
        with self.assertRaises(ValueError):
            m.replay(raw)

    def test_bad_ticks_rejected(self):
        raw = source([{"tick":0,"entities":[]},{"tick":0,"entities":[]}])
        with self.assertRaises(ValueError):
            m.replay(raw)

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            m.quantized_mm("NaN")

if __name__ == "__main__":
    unittest.main()
