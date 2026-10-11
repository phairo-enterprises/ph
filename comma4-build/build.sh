#!/usr/bin/env bash
set -euo pipefail

# Runs on GitHub Actions, not on the owner's laptop or comma four.
SOURCE_REPOSITORY="https://github.com/mvl-boston/openpilot.git"
SOURCE_BRANCH="sp-honda-dev-202608"
PINNED_SHA="cb0f8eb4e73c79e76f2c78f03dcefc79175c84f3"
TARGET_BRANCH="comma4-honda-preview-v1"

test -n "${GH_TOKEN:-}" || { echo "Missing GitHub Actions publication token" >&2; exit 1; }
git clone --single-branch --branch "$SOURCE_BRANCH" --depth=1 --filter=blob:none "$SOURCE_REPOSITORY" compiled-openpilot
cd compiled-openpilot
ACTUAL_SHA="$(git rev-parse HEAD)"
test "$ACTUAL_SHA" = "$PINNED_SHA" || { echo "Upstream moved; refusal to silently rebase $ACTUAL_SHA" >&2; exit 1; }

python3 - <<'PY'
from pathlib import Path
import ast

card = Path("openpilot/selfdrive/car/card.py")
original = 'fixed_fingerprint = (self.params.get("CarPlatformBundle") or {}).get("platform", None)'
replacement = 'fixed_fingerprint = "HONDA_ACCORD_11G"  # MAX Honda-only experimental build'
source = card.read_text()
assert source.count(original) == 1, "Fingerprinter no longer matches verified source"
card.write_text(source.replace(original, replacement, 1))
ast.parse(card.read_text(), filename=str(card))

ui = Path("openpilot/selfdrive/ui/mici/layouts/main.py")
original_ui = 'if self._onroad_time_delay is not None and rl.get_time() - self._onroad_time_delay >= ONROAD_DELAY:'
replacement_ui = 'if (self._onroad_time_delay is not None and ui_state.started and not ui_state.sm["carState"].standstill\n        and rl.get_time() - self._onroad_time_delay >= ONROAD_DELAY):'
src = ui.read_text()
assert src.count(original_ui) == 1, "Comma-four layout no longer matches verified source"
ui.write_text(src.replace(original_ui, replacement_ui, 1))
ast.parse(ui.read_text(), filename=str(ui))
print("PASS: both source patches applied and parsed")
PY

# This check is deliberately narrow. Full driving/hardware compatibility is NOT tested.
python3 -m py_compile openpilot/selfdrive/car/card.py openpilot/selfdrive/ui/mici/layouts/main.py
git checkout --orphan "$TARGET_BRANCH"
# Runtime does not need upstream CI workflows. The GitHub App token cannot
# create or change workflow files in a newly published source repository.
rm -rf .github/workflows
git add -A
git -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    -c user.name="github-actions[bot]" commit -m "MAX Honda preview: Accord fingerprint and stopped-screen behavior"

# Publish source to a distinct branch, never into ph/main.
git remote add publication "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
if git ls-remote --exit-code publication "refs/heads/$TARGET_BRANCH" >/dev/null 2>&1; then
  echo "Preview branch already exists. Refusing to overwrite it." >&2
  exit 1
fi
# LFS objects remain served by the original public sunnypilot GitLab LFS endpoint
# configured in .lfsconfig; do not attempt to push those blobs with an SSH key.
GIT_LFS_SKIP_PUSH=1 git push publication "HEAD:refs/heads/$TARGET_BRANCH"
echo "Published https://github.com/${GITHUB_REPOSITORY}/tree/${TARGET_BRANCH}"
