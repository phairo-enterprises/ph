"""Small deterministic fixed-point MAX simulation; no physical vehicle control."""
from __future__ import annotations
from dataclasses import dataclass, replace

ENGINE_VERSION = "max.kernel.v1"
QUANTUM_DENOMINATOR = 1024  # illustrative fixed-point grid; not final architect-approved value
TICK_HZ = 60                # test profile only, not final canonical tick
MAX_COORD = (1 << 60)
MAX_VEL = 1024 * 100

@dataclass(frozen=True)
class WorldState:
  tick: int = 0
  pos: tuple[int, int, int] = (0, 0, 0)
  vel: tuple[int, int, int] = (0, 0, 0)

  def record(self):
    return {"tick": self.tick, "pos": list(self.pos), "vel": list(self.vel),
            "engine_version": ENGINE_VERSION,
            "quantum_denominator": QUANTUM_DENOMINATOR}


def half_away_div(numerator: int, denominator: int) -> int:
  """Exact integer division rounded to nearest, ties away from zero."""
  if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
    raise ValueError("Integer numerator and positive integer denominator required")
  quotient, remainder = divmod(abs(numerator), denominator)
  if remainder * 2 >= denominator:
    quotient += 1
  return quotient if numerator >= 0 else -quotient


def _checked_vector(vector, bound):
  if len(vector) != 3 or any(type(v) is not int or abs(v) > bound for v in vector):
    raise ValueError("Vector outside deterministic integer bounds")
  return vector


def reduce(state: WorldState, action: tuple[int, int, int], context: dict | None = None):
  """Pure transition; state, action and deterministic context completely specify next state."""
  if context not in ({}, None):
    raise ValueError("Unrecognized context: no ambient input or randomness allowed")
  _checked_vector(state.pos, MAX_COORD)
  _checked_vector(state.vel, MAX_VEL)
  _checked_vector(action, 1)
  new_velocity = tuple(state.vel[i] + action[i] for i in range(3))
  _checked_vector(new_velocity, MAX_VEL)
  new_position = tuple(state.pos[i] + new_velocity[i] for i in range(3))
  _checked_vector(new_position, MAX_COORD)
  next_state = replace(state, tick=state.tick + 1, pos=new_position, vel=new_velocity)
  event = {"type": "max.motion.v1", "tick": next_state.tick, "action": list(action)}
  return next_state, [event]
