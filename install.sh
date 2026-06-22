#!/usr/bin/env bash
# Instalador todo-en-uno. Sirve en esta PC y en una PC nueva.
# Deja: dependencia, rclone, remoto apuntando a tu carpeta, timer cada N dias,
# GUI en el menu. Cada PC sube a su propia subcarpeta en Drive (no se pisan).
# Volve a correrlo cuando quieras para reconfigurar.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(python3 -c 'import sys; print(sys.executable)')"
RC="$HOME/.local/bin/rclone"
CFG="$HOME/.config/claude-cookie-backup"; mkdir -p "$CFG"   # config local, NO en el repo

echo "== Dependencia Python =="
"$PY" -m pip install -q --upgrade browser_cookie3

echo "== rclone =="
if [ ! -x "$RC" ] && ! command -v rclone >/dev/null; then
  echo "Instalando rclone en ~/.local/bin ..."
  ARCH=$(uname -m); case $ARCH in x86_64) A=amd64;; aarch64) A=arm64;; *) A=amd64;; esac
  curl -sfL -o /tmp/rclone.zip "https://downloads.rclone.org/rclone-current-linux-$A.zip"
  "$PY" - <<'PYEOF'
import zipfile, glob, shutil, os
zipfile.ZipFile('/tmp/rclone.zip').extractall('/tmp/rcl')
dst = os.path.expanduser('~/.local/bin/rclone')
shutil.copy(glob.glob('/tmp/rcl/*/rclone')[0], dst); os.chmod(dst, 0o755)
PYEOF
fi
RC="$(command -v rclone || echo "$HOME/.local/bin/rclone")"

if ! "$RC" listremotes 2>/dev/null | grep -q '^gdrive:'; then
  echo
  echo ">> Falta autorizar Google Drive. Corre ESTO en otra terminal:"
  echo "     $RC config"
  echo "   crea un remoto llamado 'gdrive' (tipo: drive, scope 1) y autoriza en el navegador."
  echo "   Luego vuelve a correr este install.sh."
  exit 1
fi

echo "== apunto el remoto a tu carpeta =="
FOLDER_ID="$(cat "$CFG/folder_id" 2>/dev/null || true)"
read -rp "Carpeta de Drive (pega la URL o el ID)${FOLDER_ID:+ [$FOLDER_ID]}: " IN
IN="${IN:-$FOLDER_ID}"
FOLDER_ID="$(printf '%s' "$IN" | grep -oE '[A-Za-z0-9_-]{20,}' | head -1)"
[ -n "$FOLDER_ID" ] || { echo "Falta el ID de la carpeta de Drive"; exit 1; }
printf '%s' "$FOLDER_ID" > "$CFG/folder_id"
"$PY" - "$FOLDER_ID" <<'PYEOF'
import configparser, os, sys
p = os.path.expanduser("~/.config/rclone/rclone.conf")
c = configparser.RawConfigParser(); c.read(p)
c["gdrive"]["root_folder_id"] = sys.argv[1]
with open(p, "w") as f: c.write(f)
print("root_folder_id =", sys.argv[1])
PYEOF

echo "== opciones =="
read -rp "Cada cuantos dias extraer [10]: " DAYS;  DAYS="${DAYS:-10}"
read -rp "Cuantos backups conservar [3]: " KEEP;  KEEP="${KEEP:-3}"
read -rp "URL del webhook del Sheet (vacio=no): " SHEET_WEBHOOK

UNIT="$HOME/.config/systemd/user"; mkdir -p "$UNIT" "$DIR/out"
cat > "$UNIT/claude-cookies.service" <<EOF
[Unit]
Description=Extrae cookies de claude.ai

[Service]
Type=oneshot
Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=DRIVE_FOLDER=$DIR/out
Environment=RCLONE_REMOTE=gdrive:
Environment=SHEET_WEBHOOK=$SHEET_WEBHOOK
Environment=KEEP=$KEEP
ExecStart=$PY $DIR/extract.py
EOF

cat > "$UNIT/claude-cookies.timer" <<EOF
[Unit]
Description=Cookies de claude.ai cada $DAYS dias

[Timer]
OnBootSec=5min
OnUnitActiveSec=${DAYS}d

[Install]
WantedBy=timers.target
EOF

echo "== lanzador en el menu =="
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
echo
echo "== Listo en $(hostname) =="
echo "Probar ahora:  systemctl --user start claude-cookies"
systemctl --user list-timers claude-cookies.timer --no-pager | head -2 || true
