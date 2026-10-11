"""Canonical serialization shared by input events, replays, and proof commitments."""
from __future__ import annotations
import hashlib
import json

SCHEMA_VERSION = "max.canonical.v1"


def _valid(data):
  if data is None or type(data) in (str, bool, int):
    return
  if type(data) is list:
    for item in data:
      _valid(item)
    return
  if type(data) is dict:
    if not all(type(key) is str for key in data):
      raise TypeError("All canonical object keys must be strings")
    for value in data.values():
      _valid(value)
    return
  raise TypeError(f"Unsupported canonical type: {type(data).__name__}")


def canonical_bytes(data) -> bytes:
  _valid(data)
  return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data) -> str:
  return hashlib.sha256(canonical_bytes(data)).hexdigest()


def verify_canonical(data: bytes) -> bool:
  try:
    decoded = json.loads(data)
    return canonical_bytes(decoded) == data
  except (ValueError, UnicodeError, TypeError):
    return False
