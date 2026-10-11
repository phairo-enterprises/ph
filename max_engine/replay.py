"""Deterministic replay, verified trace manifest, and render-independent ghost positions."""
from dataclasses import dataclass, field
from max_engine.canonical import canonical_bytes, digest
from max_engine.physics import ENGINE_VERSION, WorldState, reduce
from max_engine.proof import ProofChain

@dataclass
class Trace:
  actions: list[tuple[int, int, int]] = field(default_factory=list)
  initial: WorldState = field(default_factory=WorldState)

  def play(self):
    state = self.initial
    states = [state.record()]
    proof = ProofChain()
    proof.append("simulation", {"engine_version": ENGINE_VERSION, "state": states[0]}, state.tick)
    for action in self.actions:
      state, events = reduce(state, action)
      states.append(state.record())
      proof.append("simulation", {"state_hash": digest(states[-1]), "events": events}, state.tick)
    manifest = {"schema": "max.trace.v1", "engine": ENGINE_VERSION,
                "initial": states[0], "actions": [list(a) for a in self.actions],
                "state_hashes": [digest(s) for s in states], "proof_root": proof.root}
    return {"manifest": manifest, "hash": digest(manifest),
            "ghost": [s["pos"] for s in states]}

  def export_bytes(self):
    return canonical_bytes(self.play()["manifest"])

  @classmethod
  def verify(cls, manifest):
    if manifest.get("schema") != "max.trace.v1" or manifest.get("engine") != ENGINE_VERSION:
      raise ValueError("Unsupported trace version")
    state = manifest["initial"]
    t = cls(initial=WorldState(state["tick"], tuple(state["pos"]), tuple(state["vel"])),
            actions=[tuple(a) for a in manifest["actions"]])
    if t.play()["manifest"] != manifest:
      raise ValueError("Trace integrity or determinism failed")
    return t
