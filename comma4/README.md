# MAX! Comma Four observer v0.1
**Upstream:** mvl-boston/openpilot, branch sp-honda-dev-202608, SHA cb0f8eb4e73c79e76f2c78f03dcefc79175c84f3.
**Vehicle:** 2026 Honda Accord EX-L Hybrid; candidate ID HONDA_ACCORD_11G.
**Status:** standalone passive Python observer patch, NOT an installable openpilot branch.

Reads prerecorded JSONL {tick,entities:[{track_id,x_m,y_m}]}; tracks are ephemeral to a recording, not proven persistent real-world identities. Quantizes to experimental 10 mm steps and labels explanatory eight-direction QWERTY outputs as inferred, not observed. Includes original input SHA-256 and deterministic replay. No mic/horn/camera/CAN connection; no control, no bypass of vehicle or driver monitoring.

This repository is named **ph**, not **openpilot**. It cannot be installed using installer.comma.ai/phairo-enterprises/branch. To apply the patch, copy openpilot/tools/max_observer/ into the corresponding path in an actual fork of mvl-boston/openpilot. Before on-device testing, run: python3 -m unittest discover -s tests -v; then python3 openpilot/tools/max_observer/observer.py sample.jsonl.

Next: connect permitted recorded observations read-only to the shared MAX! event schema, then validate against actual device logs. Do not equate a simulated success with autonomous driving safety.
