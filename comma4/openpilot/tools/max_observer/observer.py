"""MAX! Comma Four prototype: PASSIVE observation to inferred QWERTY controls.
No vehicle or horn actuation. No driver-monitoring changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

VERSION = "max-observer-0.1.0"
QUANTUM = Decimal("0.01")  # metres, experimental


def quantized_mm(value: Any) -> int:
    d = Decimal(str(value))
    if not d.is_finite():
        raise ValueError("nonfinite coordinate")
    return int((d / QUANTUM).to_integral_value(rounding=ROUND_HALF_EVEN))


def key_for_displacement(dx: int, dy: int, deadzone: int = 1) -> str:
    if max(abs(dx), abs(dy)) <= deadzone:
        return "NONE"
    ax, ay = abs(dx), abs(dy)
    if ax * 2 <= ay:
        return "W" if dy > 0 else "S"
    if ay * 2 <= ax:
        return "D" if dx > 0 else "A"
    return {(1, 1): "E", (-1, 1): "Q", (-1, -1): "Z", (1, -1): "C"}[
        (1 if dx > 0 else -1, 1 if dy > 0 else -1)]


def replay(raw: bytes) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    seen: dict[str, tuple[int, int, int]] = {}
    events = []
    last_tick = -1
    for number, raw_line in enumerate(raw.splitlines(), 1):
        if not raw_line.strip():
            continue
        item = json.loads(raw_line)
        tick = item["tick"]
        if not isinstance(tick, int) or isinstance(tick, bool) or tick <= last_tick:
            raise ValueError(f"line {number}: ticks must strictly increase")
        last_tick = tick
        tracks_in_frame = set()
        for entity in item["entities"]:
            ident = str(entity["track_id"])
            if ident in tracks_in_frame:
                raise ValueError(f"line {number}: duplicate track in frame")
            tracks_in_frame.add(ident)
            x, y = quantized_mm(entity["x_m"]), quantized_mm(entity["y_m"])
            if ident in seen:
                t0, x0, y0 = seen[ident]
                events.append({"tick": tick, "track_id": ident,
                    "inferred_key": key_for_displacement(x-x0, y-y0),
                    "displacement_quanta": [x-x0, y-y0],
                    "dt_ticks": tick-t0, "measurement_type": "inferred",
                    "observability": "position_only_controls_ambiguous"})
            seen[ident] = (tick, x, y)
    return {"schema": "max.observer.v0", "version": VERSION,
        "source_sha256": digest, "quantum_m": str(QUANTUM),
        "binding_status": "experimental_not_canonical",
        "actuation": "disabled", "events": events}


def main():
    parser = argparse.ArgumentParser(description="Passive MAX! replay/QWERTY inference")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    serialized = json.dumps(replay(args.source.read_bytes()), sort_keys=True,
                            separators=(",", ":")) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
