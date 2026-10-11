# Comma 4 experimental build profile
Source baseline: phairo-enterprises/ph @ comma4-accord26-fingerprint-v1

## Current included code
- Fixed HONDA_ACCORD_11G platform selection for 2026 Honda Accord EX-L Hybrid.
- Standstill guard in the Mici UI transition logic.
- Experimental local-network remote components: controller.py, web.html, ui_panel.py and unit tests.
- Standalone MAX! kernel prototypes: canonical event serialization, nested input contexts, 4/26-direction quantization, basic deterministic motion, proof chain and replays.

## Feature state and exclusions
- The local Wi-Fi remote is **not activated**. Integration into the process manager and touchscreen settings menu was not completed. The files are included for development, not presented as a working remote-control interface.
- The MAX! kernel is a standalone research module, not connected to vehicle control.
- No changes to Honda steering/braking CAN logic, no driver monitoring bypass.
- No corner-alert system.
- Source boot on the actual Comma 4 and on-vehicle behavior remain untested.

## Version profiles
i1 = platform fingerprint override only.
i2 = platform fingerprint override + Mici standstill UI fix.
i3 = i2 + independent MAX kernel prototypes + isolated local Wi-Fi remote prototype source/tests.

Installer publication workflow verifies the target Git repository, branch ref, ELF architecture, embedded strings and downloaded bytes. Physical startup is a distinct test.
