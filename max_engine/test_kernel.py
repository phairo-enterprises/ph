"""Small reproducible MAX! kernel acceptance tests."""
import copy
import unittest

from max_engine.canonical import canonical_bytes, digest, verify_canonical
from max_engine.input import ContextBindings, InputEvent, DIRECTIONS_26, direction3, direction4
from max_engine.physics import WorldState, half_away_div, reduce
from max_engine.proof import ProofChain
from max_engine.replay import Trace


class TestKernel(unittest.TestCase):
  def test_canonical_order(self):
    self.assertEqual(canonical_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')
    self.assertTrue(verify_canonical(canonical_bytes({"a": [1, True, None]})))
    self.assertFalse(verify_canonical(b'{"b":2,"a":1}'))
    self.assertRaises(TypeError, digest, {"a": 1.5})

  def test_context_nesting(self):
    bindings = ContextBindings({(): {"Q": "enter:worlds"}, ("worlds",): {"W": "enter:runs"},
                                ("worlds", "runs"): {"E": "go", "X": "back"}}, "v1")
    context, command = bindings.apply((), "Q")
    self.assertEqual((context, command), (("worlds",), None))
    context, _ = bindings.apply(context, "W")
    self.assertEqual(bindings.resolve(InputEvent(1, context, "E", "keyboard", "v1")), "go")

  def test_direction_mapping(self):
    self.assertEqual(len(DIRECTIONS_26), 26)
    self.assertEqual(direction3(1000, 1000, 1000), (1, 1, 1))
    self.assertEqual(direction4(1000, 1000), (1, 0, 0))
    self.assertEqual(direction4(0, 0), (0, 0, 0))

  def test_integer_ties(self):
    self.assertEqual(half_away_div(3, 2), 2)
    self.assertEqual(half_away_div(-3, 2), -2)
    self.assertEqual(half_away_div(2, 2), 1)

  def test_reducer_purity(self):
    first, events = reduce(WorldState(), (1, 0, 0))
    self.assertEqual(first.pos, (1, 0, 0))
    self.assertEqual(first.vel, (1, 0, 0))
    self.assertEqual(first.tick, 1)
    self.assertEqual(events[0]["type"], "max.motion.v1")
    self.assertEqual(reduce(WorldState(), (1, 0, 0))[0], first)

  def test_replay_hash_consistency(self):
    t = Trace(actions=[(1, 0, 0), (0, 1, 0), (-1, 0, 1)] * 120)
    a = t.play()
    b = t.play()
    self.assertEqual(a["hash"], b["hash"])
    self.assertEqual(a["ghost"], b["ghost"])
    self.assertEqual(Trace.verify(a["manifest"]).export_bytes(), t.export_bytes())

  def test_tampered_trace_rejected(self):
    t = Trace(actions=[(1, 0, 0)] * 60)
    tampered = copy.deepcopy(t.play()["manifest"])
    tampered["state_hashes"][3] = "0" * 64
    with self.assertRaises(ValueError):
      Trace.verify(tampered)

  def test_proof_chain_modification_detected(self):
    chain = ProofChain()
    chain.append("simulation", {"velocity": 1}, 1)
    self.assertTrue(chain.verify())
    chain.events[0]["payload"]["velocity"] = 100
    self.assertFalse(chain.verify())


if __name__ == "__main__":
  unittest.main()
