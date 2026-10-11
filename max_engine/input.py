"""Nested QWERTY input contexts and discrete directional projections."""
from __future__ import annotations

from dataclasses import dataclass

DIRECTIONS_4 = ((0, -1, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0))
DIRECTIONS_26 = tuple(
  (x, y, z) for z in (-1, 0, 1) for y in (-1, 0, 1) for x in (-1, 0, 1)
  if (x, y, z) != (0, 0, 0)
)

@dataclass(frozen=True)
class InputEvent:
  tick: int
  context: tuple[str, ...]
  key: str
  source: str
  binding_version: str

  def __post_init__(self):
    if self.tick < 0 or type(self.tick) is not int:
      raise ValueError("Input tick must be nonnegative integer")
    if not self.key or not self.source or not self.binding_version:
      raise ValueError("Key, source and binding version required")

  def record(self):
    return {"tick": self.tick, "context": list(self.context), "key": self.key,
            "source": self.source, "binding_version": self.binding_version}

class ContextBindings:
  def __init__(self, mappings: dict[tuple[str, ...], dict[str, str]], version: str):
    if not version:
      raise ValueError("Version required")
    self.version = version
    self.mappings = {tuple(path): dict(binding) for path, binding in mappings.items()}

  def resolve(self, event: InputEvent) -> str:
    if event.binding_version != self.version:
      raise ValueError("Binding version mismatch")
    try:
      return self.mappings[event.context][event.key]
    except KeyError as exc:
      raise ValueError("Unbound key for context") from exc

  def apply(self, context: tuple[str, ...], key: str) -> tuple[tuple[str, ...], str | None]:
    command = self.mappings.get(context, {}).get(key)
    if command is None:
      raise ValueError("Unbound key for context")
    if command.startswith("enter:"):
      next_name = command.removeprefix("enter:")
      next_path = (*context, next_name)
      if next_path not in self.mappings:
        raise ValueError("Target context is not defined")
      return next_path, None
    if command == "back":
      return context[:-1], None
    return context, command


def quantize_axis(value: int, deadzone: int = 150, full_scale: int = 1000) -> int:
  """Map signed fixed-point stick values onto -1, 0, 1; tie behavior explicit."""
  if type(value) is not int or not (0 <= deadzone < full_scale):
    raise ValueError("Integer value and valid deadzone required")
  if not (-full_scale <= value <= full_scale):
    raise ValueError("Axis outside negotiated input range")
  if abs(value) <= deadzone:
    return 0
  return (1 if value > 0 else -1)


def direction3(x: int, y: int, z: int, *, deadzone: int = 150) -> tuple[int, int, int]:
  v = tuple(quantize_axis(a, deadzone) for a in (x, y, z))
  if v == (0, 0, 0):
    return v
  assert v in DIRECTIONS_26
  return v


def direction4(x: int, y: int, *, deadzone: int = 150) -> tuple[int, int, int]:
  vx, vy = quantize_axis(x, deadzone), quantize_axis(y, deadzone)
  if vx == vy == 0:
    return (0, 0, 0)
  # Select dominant axis; exact ties prefer X for platform-independent behavior.
  if abs(x) >= abs(y):
    return (vx or (1 if x >= 0 else -1), 0, 0)
  return (0, vy or (1 if y >= 0 else -1), 0)
