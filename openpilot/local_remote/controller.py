"""Local-only, device-approved browser controls. No CAN, steering or pedal interfaces."""
from __future__ import annotations

import fcntl
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import struct
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ADMIN_PORT = 12781
PHONE_PORT = 12782
STATE_PATH = Path(os.environ.get("LOCAL_REMOTE_STATE_PATH", "/data/local_remote/state.json"))
SAFE_SETTINGS = frozenset({"ShowDebugInfo", "IsMetric"})
PAIR_WAIT_SECONDS = 30
PAIR_EXPIRY_SECONDS = 180
SESSION_IDLE_SECONDS = 600


def wifi_ipv4():
  """Bind exclusively to the Wi-Fi device's IPv4 address, never all interfaces."""
  for name in ("wlan0", "wlan1"):
    try:
      with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        address = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", name.encode()[:15]))[20:24])
        if ipaddress.ip_address(address).is_private:
          return address
    except (OSError, ValueError):
      continue
  return None


class LocalRemote:
  def __init__(self, state_path=STATE_PATH, clock=time.monotonic):
    self.state_path = Path(state_path)
    self.clock = clock
    self.lock = threading.RLock()
    self.enabled = False
    self.panic = False
    self.temporary_open = True
    self.whitelist = set()
    self.blacklist = set()
    self.history = []
    self.known = {}
    self.pending = None
    self.session = None
    self.staged = {}
    self.ip = None
    self._load()

  def _load(self):
    try:
      data = json.loads(self.state_path.read_text())
      self.whitelist = set(data.get("whitelist", []))
      self.blacklist = set(data.get("blacklist", []))
      self.history = list(data.get("history", []))[-80:]
      self.known = dict(data.get("known", {}))
      self.temporary_open = bool(data.get("temporary_open", True))
      # Reboot defaults OFF; explicit local enabling is always required.
      self.enabled = False
      self.panic = False
    except (FileNotFoundError, ValueError, OSError, TypeError):
      self.enabled = False

  def _save(self):
    data = {"whitelist": sorted(self.whitelist), "blacklist": sorted(self.blacklist),
            "temporary_open": self.temporary_open, "history": self.history[-80:],
            "known": self.known}
    self.state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=self.state_path.parent, prefix=".localremote-")
    try:
      with os.fdopen(fd, "w") as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(data, f, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
      os.replace(temp, self.state_path)
    finally:
      if os.path.exists(temp):
        os.unlink(temp)

  def _record(self, event, device=""):
    self.history.append({"time": int(time.time()), "event": event, "device": device[:32]})
    self.history = self.history[-80:]
    self._save()

  def _clear_session(self):
    self.pending = None
    self.session = None
    self.staged = {}

  def _expire(self):
    now = self.clock()
    if self.pending and now - self.pending["created"] > PAIR_EXPIRY_SECONDS:
      self._record("request_expired", self.pending["device"])
      self.pending = None
    if self.session and (now - self.session["last"] > SESSION_IDLE_SECONDS):
      self._record("session_expired", self.session["device"])
      self._clear_session()

  def _ban(self, device, reason):
    self.blacklist.add(device)
    self.whitelist.discard(device)
    self.panic = True
    self.enabled = False
    self._clear_session()
    self._record(reason, device)

  def _target(self):
    if self.pending:
      return self.pending["device"]
    if self.session:
      return self.session["device"]
    return ""

  def status(self):
    with self.lock:
      self._expire()
      p = self.pending
      s = self.session
      return {
        "enabled": self.enabled, "panic": self.panic,
        "temporary_open": self.temporary_open,
        "endpoint": "http://" + self.ip + ":" + str(PHONE_PORT) if self.enabled and self.ip else "",
        "pending": ({"name": p["name"], "device": p["device"], "code": p["code"],
                     "approved": p["approved"] is not None,
                     "wait": max(0, int(PAIR_WAIT_SECONDS - (self.clock() - p["approved"]))) if p["approved"] else 0}
                    if p else None),
        "active": {"name": s["name"], "device": s["device"]} if s else None,
        "staged": self.staged.copy(),
        "whitelist": sorted(self.whitelist),
        "blacklist": sorted(self.blacklist),
        "history": self.history[-15:],
      }

  def admin(self, action, data=None):
    data = data or {}
    with self.lock:
      self._expire()
      if action == "status":
        return self.status()
      if action == "enable":
        self.enabled = bool(data.get("value")) and not self.panic
        if not self.enabled:
          self._clear_session()
        self._record("enabled" if self.enabled else "disabled")
      elif action == "open_mode":
        self.temporary_open = bool(data.get("value"))
        self._record("open_mode" if self.temporary_open else "whitelist_only")
      elif action == "approve":
        if not self.pending or self.pending["approved"] is not None:
          return {"error": "no_pending_request"}
        self.pending["approved"] = self.clock()
        self._record("device_approved", self.pending["device"])
      elif action == "reject":
        if self.pending:
          self._record("device_rejected", self.pending["device"])
        self.pending = None
      elif action == "kick":
        if self.session:
          self._record("session_kicked", self.session["device"])
        self._clear_session()
      elif action == "trust":
        device = str(data.get("device", self._target()))
        if not re.fullmatch(r"[0-9a-f]{32}", device):
          return {"error": "no_device"}
        self.whitelist.add(device)
        self.blacklist.discard(device)
        self._record("whitelisted", device)
      elif action == "block":
        device = str(data.get("device", self._target()))
        if not re.fullmatch(r"[0-9a-f]{32}", device):
          return {"error": "no_device"}
        self.blacklist.add(device)
        self.whitelist.discard(device)
        if self._target() == device:
          self._clear_session()
        self._record("permanent_block", device)
      elif action == "unblock":
        device = str(data.get("device", ""))
        self.blacklist.discard(device)
        self._record("unblocked", device)
      elif action == "panic":
        device = self._target()
        if device:
          self._ban(device, "manual_panic")
        else:
          self.panic = True
          self.enabled = False
          self._clear_session()
          self._record("manual_panic")
      elif action == "clear_panic":
        self.panic = False
        self.enabled = False
        self._record("panic_cleared")
      elif action == "commit":
        # Actual Params writes must occur only in the touchscreen UI callback.
        self.staged.clear()
        self._record("changes_confirmed")
      elif action == "discard":
        self.staged.clear()
        self._record("changes_discarded")
      else:
        return {"error": "unknown_action"}
      return self.status()

  def client(self, action, data, peer):
    with self.lock:
      self._expire()
      if not self.enabled or self.panic:
        return {"error": "disabled"}
      if action == "join":
        if self.pending or self.session:
          return {"error": "one_device_at_a_time"}
        device = str(data.get("device", ""))
        name = re.sub(r"[^a-zA-Z0-9 _.-]", "", str(data.get("name", "")))[:32].strip() or "Unknown phone"
        if not re.fullmatch(r"[0-9a-f]{32}", device):
          return {"error": "invalid_device"}
        if device in self.blacklist or (not self.temporary_open and device not in self.whitelist):
          self._record("connection_denied", device)
          return {"error": "blocked"}
        correct = str(secrets.randbelow(900000) + 100000)
        choices = {correct}
        while len(choices) < 3:
          choices.add(str(secrets.randbelow(900000) + 100000))
        choices = sorted(choices)
        self.pending = {"id": secrets.token_hex(16), "device": device,
                        "name": name, "peer": peer, "code": correct, "choices": choices,
                        "created": self.clock(), "approved": None}
        self.known[device] = name
        self._record("connection_requested", device)
        return {"request": self.pending["id"], "choices": choices, "state": "await_device_approval"}
      if action == "poll":
        p = self.pending
        if p and hmac.compare_digest(str(data.get("request", "")), p["id"]) and peer == p["peer"]:
          if p["approved"] is None:
            return {"state": "await_device_approval"}
          seconds = PAIR_WAIT_SECONDS - (self.clock() - p["approved"])
          return {"state": "verify" if seconds <= 0 else "no_commands",
                  "remaining": max(0, int(seconds))}
        return {"state": "not_pending"}
      if action == "prove":
        p = self.pending
        if not p or not hmac.compare_digest(str(data.get("request", "")), p["id"]) or peer != p["peer"]:
          return {"error": "not_pending"}
        if p["approved"] is None or self.clock() - p["approved"] < PAIR_WAIT_SECONDS:
          return {"error": "wait_30_seconds"}
        code = str(data.get("code", ""))
        if not hmac.compare_digest(code, p["code"]):
          self._ban(p["device"], "bad_pairing_code_panic")
          return {"error": "panic_blocked"}
        token = secrets.token_urlsafe(32)
        self.session = {"token": token, "device": p["device"], "name": p["name"],
                        "peer": peer, "last": self.clock()}
        self.pending = None
        self._record("paired", self.session["device"])
        return {"state": "connected", "token": token}
      s = self.session
      token = str(data.get("token", ""))
      if not s or peer != s["peer"] or not hmac.compare_digest(token, s["token"]):
        return {"error": "unauthorized"}
      s["last"] = self.clock()
      if action == "stage":
        key = str(data.get("key", ""))
        value = data.get("value")
        if key not in SAFE_SETTINGS or type(value) is not bool:
          return {"error": "not_an_allowed_setting"}
        self.staged[key] = value
        self._record("change_staged", s["device"])
        return {"state": "staged", "staged": self.staged.copy()}
      if action == "disconnect":
        self._record("disconnected", s["device"])
        self._clear_session()
        return {"state": "disconnected"}
      return {"error": "unknown_action"}


def make_handler(state, admin=False):
  class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
      pass  # No pairing secrets or device names in HTTP access logs.

    def _reply(self, obj, status=200, mime="application/json"):
      raw = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
      self.send_response(status)
      self.send_header("Content-Type", mime)
      self.send_header("Content-Length", str(len(raw)))
      self.send_header("Cache-Control", "no-store, max-age=0")
      self.send_header("X-Content-Type-Options", "nosniff")
      self.send_header("X-Frame-Options", "DENY")
      if mime.startswith("text/html"):
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'self'")
      self.end_headers()
      self.wfile.write(raw)

    def do_GET(self):
      if admin:
        self._reply({"error": "POST_only"}, 405)
      elif urlsplit(self.path).path == "/":
        self._reply(Path(__file__).with_name("web.html").read_bytes(), mime="text/html; charset=utf-8")
      else:
        self._reply({"error": "not_found"}, 404)

    def do_POST(self):
      if urlsplit(self.path).path != "/api":
        self._reply({"error": "not_found"}, 404)
        return
      if not admin:
        origin = self.headers.get("Origin")
        expected = "http://" + str(self.server.server_address[0]) + ":" + str(PHONE_PORT)
        if origin != expected:
          self._reply({"error": "origin_denied"}, 403)
          return
      if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
        self._reply({"error": "json_only"}, 415)
        return
      try:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 4096:
          raise ValueError("invalid body length")
        body = json.loads(self.rfile.read(length))
        if not isinstance(body, dict):
          raise ValueError("not an object")
        action = str(body.pop("action", ""))
        response = state.admin(action, body) if admin else state.client(action, body, self.client_address[0])
        self._reply(response)
      except (ValueError, UnicodeError, TypeError, KeyError):
        self._reply({"error": "invalid_request"}, 400)
  return Handler


class ReusableServer(ThreadingHTTPServer):
  allow_reuse_address = True
  daemon_threads = True


def serve_forever():
  controller = LocalRemote()
  admin_server = ReusableServer(("127.0.0.1", ADMIN_PORT), make_handler(controller, True))
  threading.Thread(target=admin_server.serve_forever, daemon=True).start()
  phone_server = None
  bound_ip = None
  try:
    while True:
      with controller.lock:
        enabled = controller.enabled and not controller.panic
      ip = wifi_ipv4() if enabled else None
      if ip != bound_ip:
        if phone_server is not None:
          phone_server.shutdown()
          phone_server.server_close()
          phone_server = None
        bound_ip = None
        with controller.lock:
          controller.ip = None
          if controller.session or controller.pending:
            controller._clear_session()
        if ip is not None:
          try:
            phone_server = ReusableServer((ip, PHONE_PORT), make_handler(controller))
            bound_ip = ip
            with controller.lock:
              controller.ip = ip
            threading.Thread(target=phone_server.serve_forever, daemon=True).start()
          except OSError:
            phone_server = None
      time.sleep(1)
  finally:
    if phone_server is not None:
      phone_server.shutdown()
      phone_server.server_close()
    admin_server.shutdown()
    admin_server.server_close()


if __name__ == "__main__":
  serve_forever()
