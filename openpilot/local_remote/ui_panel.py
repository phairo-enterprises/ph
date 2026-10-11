"""Mici touchscreen controls for local remote. All approvals happen on this screen."""
import json
import time
from urllib.request import Request, urlopen

from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.selfdrive.ui.mici.widgets.dialog import BigConfirmationDialog
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets.scroller import NavScroller
from openpilot.selfdrive.ui.ui_state import ui_state

ADMIN = "http://127.0.0.1:12781/api"
ALLOWED_PARAMS = frozenset(("ShowDebugInfo", "IsMetric"))


def local_api(action, **kwargs):
  try:
    data = json.dumps({"action": action, **kwargs}).encode()
    req = Request(ADMIN, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=0.20) as response:
      return json.load(response)
  except (OSError, ValueError):
    return {"error": "local_remote_service_unavailable"}


class LocalRemoteLayout(NavScroller):
  def __init__(self):
    super().__init__()
    self._state = {}
    self._last_update = 0.
    self._params = Params()
    self._icon = gui_app.texture("icons_mici/settings/network/wifi_strength_full.png", 64, 56)

    self._enable = self._button("Local Remote", self._toggle)
    self._endpoint = self._button("Phone URL", self._refresh)
    self._pair = self._button("Confirm Device", self._approve)
    self._reject = self._button("Reject Device", lambda: self._act("reject"))
    self._kick = self._button("Kick Connection", lambda: self._act("kick"))
    self._trust = self._button("Whitelist Device", lambda: self._act("trust"))
    self._block = self._button("Block Permanently", lambda: self._act("block"))
    self._mode = self._button("Access Policy", self._toggle_mode)
    self._changes = self._button("Confirm Changes", self._confirm_changes)
    self._discard = self._button("Discard Changes", lambda: self._act("discard"))
    self._panic = self._button("Panic Block", lambda: self._act("panic"))
    self._clear = self._button("Clear Panic", lambda: self._act("clear_panic"))
    self._unblock = self._button("Unblock Device", self._unblock_first)
    self._history = self._button("Connection History", self._refresh)

    self._scroller.add_widgets([
      self._enable, self._endpoint, self._pair, self._reject,
      self._kick, self._trust, self._block, self._mode, self._changes,
      self._discard, self._panic, self._clear, self._unblock, self._history,
    ])
    self._refresh()

  def _button(self, title, callback):
    item = BigButton(title, "")
    item.set_click_callback(callback)
    return item

  def _act(self, action, **kwargs):
    local_api(action, **kwargs)
    self._refresh()

  def _refresh(self):
    self._state = local_api("status")
    self._last_update = time.monotonic()
    p = self._state.get("pending") or {}
    a = self._state.get("active") or {}
    staged = self._state.get("staged") or {}
    last = (self._state.get("history") or [{}])[-1]
    self._enable.set_value("ON" if self._state.get("enabled") else "OFF")
    self._endpoint.set_value(self._state.get("endpoint") or "Wi-Fi not enabled")
    self._pair.set_value(("%s | code %s | %ss" % (p.get("name",""), p.get("code",""), p.get("wait", 0))) if p else "No request")
    self._reject.set_value(p.get("name", "No request"))
    self._kick.set_value(a.get("name", "No connection"))
    self._trust.set_value((p or a).get("name", "No device"))
    self._block.set_value((p or a).get("name", "No device"))
    self._mode.set_value("Open temporarily" if self._state.get("temporary_open") else "Whitelist only")
    self._changes.set_value(", ".join("%s=%s" % (k, v) for k, v in staged.items()) or "No pending changes")
    self._discard.set_value("%s proposal(s)" % len(staged))
    self._panic.set_value("Disabled" if self._state.get("panic") else "Immediately revoke access")
    self._clear.set_value("Blocked" if self._state.get("panic") else "Not blocked")
    self._unblock.set_value("%s blocked" % len(self._state.get("blacklist") or []))
    self._history.set_value("%s: %s" % (last.get("event", ""), str(last.get("device",""))[:6]))

  def _update_state(self):
    super()._update_state()
    if time.monotonic() - self._last_update > 1:
      self._refresh()

  def _toggle(self):
    self._act("enable", value=not self._state.get("enabled", False))

  def _toggle_mode(self):
    self._act("open_mode", value=not self._state.get("temporary_open", True))

  def _approve(self):
    pending = self._state.get("pending")
    if not pending or pending.get("approved"):
      return
    label = "%s: %s" % (pending.get("name", "Phone"), pending.get("code", ""))
    gui_app.push_widget(BigConfirmationDialog(
      "Confirm Device " + label, self._icon, confirm_callback=lambda: self._act("approve")))

  def _unblock_first(self):
    blocked = self._state.get("blacklist") or []
    if blocked:
      self._act("unblock", device=blocked[0])

  def _confirm_changes(self):
    changes = dict(self._state.get("staged") or {})
    if not changes or not set(changes).issubset(ALLOWED_PARAMS):
      return

    def commit():
      # Re-read the queue after the local touch confirmation; reject races.
      latest = local_api("status").get("staged", {})
      if latest != changes or ui_state.engaged:
        self._refresh()
        return
      for key, value in latest.items():
        if key in ALLOWED_PARAMS and type(value) is bool:
          self._params.put_bool(key, value)
      self._act("commit")

    gui_app.push_widget(BigConfirmationDialog(
      "Confirm Changes", self._icon, confirm_callback=commit))
