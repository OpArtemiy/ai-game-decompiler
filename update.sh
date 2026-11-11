#!/usr/bin/env bash
# Run on the server:  bash ~/decompiler-v2/update.sh
# Backs up the current app, installs this version, runs the tests and restarts the service.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HOME/app"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$HOME/app-backup-$STAMP"

command -v rsync >/dev/null || sudo apt-get install -y rsync

echo "1/6 Backing up $APP to $BACKUP (without venv and jobs)"
mkdir -p "$BACKUP"
rsync -a --exclude venv --exclude jobs --exclude __pycache__ "$APP/" "$BACKUP/"

OLD_MODEL=""
if [ -f "$APP/ai.py" ]; then
  OLD_MODEL="$(grep -oP "get\('MODEL', '\K[^']+" "$APP/ai.py" 2>/dev/null | head -1 || true)"
fi

echo "2/6 Copying the new version"
rsync -a --exclude venv --exclude jobs --exclude __pycache__ --exclude update.sh "$SRC/" "$APP/"

echo "3/6 Installing Python packages"
cd "$APP"
source venv/bin/activate
pip install -q -r requirements.txt

echo "4/6 Running the tests"
python tests/run_tests.py
python tests/smoke_main.py

echo "5/6 Settings file for the service"
OVERRIDE_DIR=/etc/systemd/system/decompiler.service.d
if [ ! -f "$OVERRIDE_DIR/override.conf" ]; then
  sudo mkdir -p "$OVERRIDE_DIR"
  sudo cp deploy/override.conf.example "$OVERRIDE_DIR/override.conf"
  if [ -n "$OLD_MODEL" ]; then
    sudo sed -i "s#^Environment=MODEL=.*#Environment=MODEL=$OLD_MODEL#" "$OVERRIDE_DIR/override.conf"
  fi
  echo "   Created $OVERRIDE_DIR/override.conf (MODEL=${OLD_MODEL:-default})"
else
  echo "   $OVERRIDE_DIR/override.conf already exists, left unchanged"
fi

echo "6/6 Restarting the service"
sudo systemctl daemon-reload
sudo systemctl restart decompiler
sleep 2
sudo systemctl status decompiler --no-pager | head -6
echo
echo "Done. Backup of the old version: $BACKUP"
echo "To go back:  rsync -a $BACKUP/ $APP/ && sudo systemctl restart decompiler"
