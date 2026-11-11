#!/usr/bin/env bash
# OPTIONAL (Day 3): installs Java and jadx so that Java/Android apps can be decompiled. Run on the server.
set -euo pipefail
sudo apt-get update
sudo apt-get install -y default-jre-headless unzip curl
URL="$(curl -s https://api.github.com/repos/skylot/jadx/releases/latest | grep browser_download_url | grep -E 'jadx-[0-9.]+\.zip' | head -1 | cut -d'"' -f4)"
[ -n "$URL" ] || { echo "Could not find the jadx download. Check https://github.com/skylot/jadx/releases"; exit 1; }
echo "Downloading $URL"
curl -L -o /tmp/jadx.zip "$URL"
sudo rm -rf /opt/jadx && sudo mkdir -p /opt/jadx
sudo unzip -q /tmp/jadx.zip -d /opt/jadx
sudo chmod +x /opt/jadx/bin/jadx
sudo ln -sf /opt/jadx/bin/jadx /usr/local/bin/jadx
jadx --version
echo "jadx installed. Restart the service:  sudo systemctl restart decompiler"
