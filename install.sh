#!/usr/bin/env bash
# Instalador todo-en-uno para Linux (systemd) y macOS (launchd).
# Deja: dependencia, rclone, remoto a tu carpeta, config.json, agendador
# diario (extract.py --scheduled se auto-regula segun "days") y la GUI.
# Cada PC sube a su propia subcarpeta en Drive. Re-corrible para reconfigurar.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(python3 -c 'import sys; print(sys.executable)')"
OS="$(uname -s)"
CFGDIR="$HOME/.config/claude-cookie-backup"; mkdir -p "$CFGDIR"
RC="$HOME/.local/bin/rclone"

echo "== Dependencia Python =="
"$PY" -m pip install -q --upgrade browser_cookie3

echo "== rclone =="
if [ ! -x "$RC" ] && ! command -v rclone >/dev/null; then
  echo "Instalando rclone en ~/.local/bin ..."
  case "$OS" in Darwin) P=osx;; *) P=linux;; esac
  case "$(uname -m)" in x86_64|amd64) A=amd64;; arm64|aarch64) A=arm64;; *) A=amd64;; esac
  curl -sfL -o /tmp/rclone.zip "https://downloads.rclone.org/rclone-current-$P-$A.zip"
  "$PY" - <<'PYEOF'
import zipfile, glob, shutil, os
zipfile.ZipFile('/tmp/rclone.zip').extractall('/tmp/rcl')
dst = os.path.expanduser('~/.local/bin/rclone')
os.makedirs(os.path.dirname(dst), exist_ok=True)
shutil.copy(glob.glob('/tmp/rcl/*/rclone')[0], dst); os.chmod(dst, 0o755)
PYEOF
fi
RC="$(command -v rclone || echo "$HOME/.local/bin/rclone")"

if ! "$RC" listremotes 2>/dev/null | grep -q '^gdrive:'; then
  echo ">> Falta autorizar Drive. Corre:  $RC config"
  echo "   crea remoto 'gdrive' (tipo drive, scope 1), autoriza, y re-corre este script."
  exit 1
fi

echo "== apunto el remoto a tu carpeta de Drive =="
FOLDER_ID="$(cat "$CFGDIR/folder_id" 2>/dev/null || true)"
read -rp "Carpeta de Drive (URL o ID)${FOLDER_ID:+ [$FOLDER_ID]}: " IN
IN="${IN:-$FOLDER_ID}"
FOLDER_ID="$(printf '%s' "$IN" | grep -oE '[A-Za-z0-9_-]{20,}' | head -1)"
[ -n "$FOLDER_ID" ] || { echo "Falta el ID"; exit 1; }
printf '%s' "$FOLDER_ID" > "$CFGDIR/folder_id"
"$PY" - "$FOLDER_ID" <<'PYEOF'
import configparser, os, sys
p = os.path.expanduser("~/.config/rclone/rclone.conf")
c = configparser.RawConfigParser(); c.read(p)
c["gdrive"]["root_folder_id"] = sys.argv[1]
with open(p, "w") as f: c.write(f)
PYEOF

echo "== opciones =="
read -rp "Cada cuantos dias [15]: " DAYS;  DAYS="${DAYS:-15}"
read -rp "Cuantos backups conservar [3]: " KEEP;  KEEP="${KEEP:-3}"
read -rp "URL del webhook del Sheet (vacio=no): " SHEET

mkdir -p "$DIR/out"
"$PY" - "$DIR/out" "$DAYS" "$KEEP" "$SHEET" <<'PYEOF'
import json, os, sys
folder, days, keep, sheet = sys.argv[1:5]
cfg = {"drive_folder": folder, "rclone_remote": "gdrive:", "sheet_webhook": sheet,
       "keep": int(keep), "days": int(days), "browser": ""}
d = os.path.expanduser("~/.config/claude-cookie-backup"); os.makedirs(d, exist_ok=True)
json.dump(cfg, open(os.path.join(d, "config.json"), "w"), indent=2)
print("config.json escrito")
PYEOF

if [ "$OS" = "Darwin" ]; then
  echo "== agendador macOS (launchd) =="
  PL="$HOME/Library/LaunchAgents/com.claudecookies.backup.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PL" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.claudecookies.backup</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$DIR/extract.py</string><string>--scheduled</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>86400</integer>
</dict></plist>
EOF
  launchctl unload "$PL" 2>/dev/null || true
  launchctl load "$PL"
  echo "launchd cargado. Probar: $PY $DIR/extract.py"
else
  echo "== agendador Linux (systemd --user) =="
  UNIT="$HOME/.config/systemd/user"; mkdir -p "$UNIT"
  cat > "$UNIT/claude-cookies.service" <<EOF
[Unit]
Description=Extrae cookies de claude.ai

[Service]
Type=oneshot
Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$PY $DIR/extract.py --scheduled
EOF
  cat > "$UNIT/claude-cookies.timer" <<EOF
[Unit]
Description=Chequeo diario de cookies de claude.ai (se auto-regula segun config)

[Timer]
OnBootSec=5min
OnUnitActiveSec=1d

[Install]
WantedBy=timers.target
EOF
  mkdir -p "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/applications/claude-cookie-backup.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude · Cookie Backup
Comment=Extrae y copia los cookies de claude.ai
Exec=$PY $DIR/gui.py
Icon=$DIR/assets/logo.svg
Terminal=false
Categories=Utility;
EOF
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
  systemctl --user daemon-reload
  systemctl --user enable --now claude-cookies.timer
  systemctl --user list-timers claude-cookies.timer --no-pager | head -2 || true
fi

echo "== Listo en $(hostname) ($OS) =="
echo "Extraer ahora:  $PY $DIR/extract.py"
echo "Interfaz:       $PY $DIR/gui.py"
