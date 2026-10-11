"""Proof commitments with explicit observational and simulated distinctions."""
from __future__ import annotations
from dataclasses import dataclass, field
from max_engine.canonical import digest

EVENT_SCHEMA = "eop.event.v1"
EVIDENCE_KINDS = frozenset(("observation", "inference", "simulation", "assertion"))

@dataclass
class ProofChain:
  events: list[dict] = field(default_factory=list)
  root: str = "0" * 64

  def append(self, kind: str, payload: dict, tick: int, *, origin: str = "max_engine"):
    if kind not in EVIDENCE_KINDS:
      raise ValueError("Evidence kind required")
    if type(tick) is not int or tick < 0:
      raise ValueError("Nonnegative integer tick required")
    if self.events and tick < self.events[-1]["tick"]:
      raise ValueError("Proof ticks may not move backward")
    if not isinstance(payload, dict):
      raise TypeError("Event payload must be object")
    event = {"schema": EVENT_SCHEMA, "tick": tick,
             "evidence_kind": kind, "origin": origin,
             "previous": self.root, "payload": payload}
    event["id"] = digest(event)
    self.events.append(event)
    self.root = event["id"]
    return event

  def verify(self) -> bool:
    prior = "0" * 64
    last_tick = -1
    for event in self.events:
      event_body = {k: v for k, v in event.items() if k != "id"}
      if (event.get("previous") != prior or event["id"] != digest(event_body)
          or event.get("evidence_kind") not in EVIDENCE_KINDS
          or event.get("tick", -1) < last_tick):
        return False
      last_tick = event["tick"]
      prior = event["id"]
    return prior == self.root
