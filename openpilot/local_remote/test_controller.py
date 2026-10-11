"""Offline tests for local-only controls. No device, CAN, or driving code imported."""
import tempfile
from pathlib import Path
import unittest

from openpilot.local_remote.controller import LocalRemote, PAIR_WAIT_SECONDS


class Clock:
  def __init__(self):
    self.value = 1000

  def __call__(self):
    return self.value

  def advance(self, seconds):
    self.value += seconds


class LocalRemoteTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.path = Path(self.temp.name) / "state.json"
    self.clock = Clock()
    self.remote = LocalRemote(self.path, self.clock)
    self.device = "0123456789abcdef0123456789abcdef"
    self.peer = "192.168.3.10"
    self.remote.admin("enable", value=True)

  def join(self):
    return self.remote.client("join", {"device": self.device, "name": "Test Phone"}, self.peer)

  def pair(self):
    result = self.join()
    self.assertEqual(len(result["choices"]), 3)
    self.remote.admin("approve")
    self.clock.advance(PAIR_WAIT_SECONDS)
    code = self.remote.status()["pending"]["code"]
    result = self.remote.client("prove", {"request": result["request"], "code": code}, self.peer)
    self.assertEqual(result["state"], "connected")
    return result["token"]

  def test_disabled_by_default_after_restart(self):
    self.remote.admin("enable", value=False)
    clone = LocalRemote(self.path, self.clock)
    self.assertFalse(clone.status()["enabled"])

  def test_one_device_pending_and_session(self):
    first = self.join()
    self.assertEqual(first["state"], "await_device_approval")
    self.assertEqual(self.remote.client("join", {"device": self.device}, self.peer)["error"], "one_device_at_a_time")
    self.remote.admin("approve")
    self.clock.advance(PAIR_WAIT_SECONDS)
    code = self.remote.status()["pending"]["code"]
    token = self.remote.client("prove", {"request": first["request"], "code": code}, self.peer)["token"]
    self.assertTrue(token)
    self.assertEqual(self.remote.client("join", {"device": self.device}, self.peer)["error"], "one_device_at_a_time")

  def test_hold_rejects_command_and_early_verification(self):
    result = self.join()
    self.remote.admin("approve")
    code = self.remote.status()["pending"]["code"]
    self.assertEqual(self.remote.client("prove", {"request": result["request"], "code": code}, self.peer)["error"], "wait_30_seconds")
    self.assertEqual(self.remote.client("stage", {"token": "bad", "key": "IsMetric", "value": True}, self.peer)["error"], "unauthorized")
    self.assertEqual(self.remote.status()["staged"], {})

  def test_wrong_decoy_panics_and_blocks(self):
    result = self.join()
    self.remote.admin("approve")
    self.clock.advance(31)
    correct = self.remote.status()["pending"]["code"]
    wrong = next(x for x in result["choices"] if x != correct)
    self.assertEqual(self.remote.client("prove", {"request": result["request"], "code": wrong}, self.peer)["error"], "panic_blocked")
    s = self.remote.status()
    self.assertTrue(s["panic"])
    self.assertFalse(s["enabled"])
    self.assertIn(self.device, s["blacklist"])
    clone = LocalRemote(self.path, self.clock)
    self.assertIn(self.device, clone.status()["blacklist"])

  def test_session_tokens_and_staged_changes(self):
    token = self.pair()
    self.assertEqual(self.remote.client("stage", {"token": "bad", "key": "ShowDebugInfo", "value": True}, self.peer)["error"], "unauthorized")
    self.assertEqual(self.remote.client("stage", {"token": token, "key": "OpenpilotEnabledToggle", "value": True}, self.peer)["error"], "not_an_allowed_setting")
    self.assertEqual(self.remote.client("stage", {"token": token, "key": "IsMetric", "value": 1}, self.peer)["error"], "not_an_allowed_setting")
    out = self.remote.client("stage", {"token": token, "key": "IsMetric", "value": True}, self.peer)
    self.assertEqual(out["staged"], {"IsMetric": True})
    # The service does not import Params or write vehicle settings.
    self.remote.admin("discard")
    self.assertEqual(self.remote.status()["staged"], {})

  def test_whitelist_policy_and_kick(self):
    token = self.pair()
    self.remote.admin("trust")
    self.assertIn(self.device, self.remote.status()["whitelist"])
    self.remote.admin("kick")
    self.assertIsNone(self.remote.status()["active"])
    self.remote.admin("open_mode", value=False)
    unknown = "f" * 32
    self.assertEqual(self.remote.client("join", {"device": unknown}, self.peer)["error"], "blocked")
    self.assertEqual(self.remote.client("join", {"device": self.device}, self.peer)["state"], "await_device_approval")

  def test_session_expiry_and_panic(self):
    token = self.pair()
    self.clock.advance(601)
    self.assertIsNone(self.remote.status()["active"])
    self.assertEqual(self.remote.client("stage", {"token": token, "key": "IsMetric", "value": True}, self.peer)["error"], "unauthorized")
    self.remote.admin("panic")
    self.assertTrue(self.remote.status()["panic"])
    self.remote.admin("clear_panic")
    self.assertFalse(self.remote.status()["enabled"])

  def test_join_timeout(self):
    self.join()
    self.clock.advance(181)
    self.assertIsNone(self.remote.status()["pending"])


if __name__ == "__main__":
  unittest.main()
