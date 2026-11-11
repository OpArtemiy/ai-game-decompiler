#!/usr/bin/env bash
# Pulls the managed code DLLs out of a Unity PC build (.zip) or an Android build (.apk), so you only upload a few MB.
# Usage:  bash extract_dll.sh path/to/DarkestDungeon.zip     (or an .apk)
set -euo pipefail
FILE="${1:?Usage: extract_dll.sh path/to/game.zip-or-apk}"
OUT="${2:-./extracted}"
mkdir -p "$OUT"

if unzip -l "$FILE" | grep -qiE 'GameAssembly|libil2cpp|global-metadata'; then
  echo "WARNING: this looks like an IL2CPP build. The decompiler only supports Unity Mono builds."
fi

unzip -j -o "$FILE" '*Managed/Assembly-CSharp*.dll' -d "$OUT" || {
  echo "No Assembly-CSharp*.dll found in $FILE (is it a Unity Mono build?)"; exit 1; }
echo
echo "Extracted to $OUT:"
ls -la "$OUT"
echo "Upload Assembly-CSharp.dll (and optionally Assembly-CSharp-firstpass.dll) to the website."
