#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DST="$HOME/.gemini/config/plugins/claude-stack"
AGY_CLI_DIR="$HOME/.gemini/antigravity-cli"
HUD_DST="$AGY_CLI_DIR/hud"
SETTINGS_FILE="$AGY_CLI_DIR/settings.json"

echo "[1/4] Installing global plugin -> $PLUGIN_DST"
mkdir -p "$HOME/.gemini/config/plugins"
rm -rf "$PLUGIN_DST"
cp -R "$REPO_DIR/plugins/claude-stack" "$PLUGIN_DST"
rm -rf "$PLUGIN_DST/hooks/__pycache__"

echo "[2/4] Installing 3-line HUD statusLine -> $HUD_DST"
mkdir -p "$HUD_DST"
cp "$REPO_DIR/hud/hud.mjs" "$REPO_DIR/hud/test_hud.mjs" "$HUD_DST/"
chmod +x "$HUD_DST/hud.mjs"

echo "[3/4] Merging altScreenMode, statusLine & 512K contextWindow into $SETTINGS_FILE"
python3 - "$SETTINGS_FILE" <<'PY'
import json, os, shutil, sys

path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
data = {}
if os.path.exists(path):
    shutil.copy2(path, path + ".bak")
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
        if content:
            data = json.loads(content)

data["altScreenMode"] = "always"
data.setdefault("contextWindow", "512K")
data["statusLine"] = {
    "type": "command",
    "command": "node ~/.gemini/antigravity-cli/hud/hud.mjs",
    "enabled": True,
    "padding": 0,
    "stack_with_default": False,
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
os.chmod(path, 0o600)
if os.path.exists(path + ".bak"):
    os.remove(path + ".bak")
PY

echo "[4/4] Running verification gates..."
for t in "$PLUGIN_DST"/hooks/test_*.py; do
  python3 "$t"
done
if command -v node >/dev/null 2>&1; then
  node --test "$HUD_DST/test_hud.mjs"
fi
if command -v agy >/dev/null 2>&1; then
  agy plugin validate "$PLUGIN_DST" --strict
  agy plugin enable claude-stack >/dev/null 2>&1 || true
fi

echo "Done! Restart agy (e.g. exit and run 'agy -c') to enjoy full-screen (altscreen) mode and your new setup."
