# MAX! Comma Four observer v0.1
**Source:** mvl-boston/openpilot, branch sp-honda-dev-202608, pinned upstream SHA `cb0f8eb4e73c79e76f2c78f03dcefc79175c84f3`.
**Vehicle:** 2026 Honda Accord EX-L Hybrid; candidate ID `HONDA_ACCORD_11G`.
**Status:** Published standalone, passive Python observation-to-QWERTY test; **not** an installable openpilot fork.

This development patch is stored under `comma4/` in the existing public `phairo-enterprises/ph` repository. A comma.ai installer of the form `installer.comma.ai/OWNER/BRANCH` expects an accessible `OWNER/openpilot` repository, which does not exist in the connected GitHub account. This branch must not be entered into the device as an installation URL.

## What can be tested now
From this repository's root:

```sh
cd comma4
python3 -m unittest discover -s tests -v
python3 openpilot/tools/max_observer/observer.py sample.jsonl -o sample_replay.json
```

The sample is synthetic JSONL with `tick` and ephemeral `track_id` positions. The observer converts successive positions into **inferred** directional QWERTY keys using a provisional 10 mm quantum. All inferences are explanatory, not evidence of actual driver inputs. Replay contains deterministic quantized displacements and input SHA-256.

There is **no** live camera, CAN, horn or microphone integration, vehicle actuation, vehicle recognition patch, driver-monitoring change, or on-device result.

## Installation milestone, still blocked
1. An independently created writable `phairo-enterprises/openpilot` fork of the exact upstream branch is required.
2. Copy the observer code into that fork's `openpilot/tools/max_observer/` directory and add the regression tests.
3. Confirm comma four runtime compatibility, dependencies, test results and installation before representing `phairo-enterprises/BRANCH` as valid.
4. Any later connection to vehicle telemetry is read-only, retaining stock driving safeguards.

The earlier objective of a custom driving build remains separate from this safe simulation/observation cut.
