#!/usr/bin/env bash
# Builds tests/fixtures/dummy.apk, an empty app the device tests install and expect Anchor to block.
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
BT="$SDK/build-tools/$(ls "$SDK/build-tools" | sort -V | tail -1)"
PLATFORM="$SDK/platforms/$(ls "$SDK/platforms" | sort -V | tail -1)/android.jar"
TMP=$(mktemp -d)
"$BT/aapt2" link -I "$PLATFORM" --manifest dummy/AndroidManifest.xml -o "$TMP/unsigned.apk" \
  --min-sdk-version 29 --target-sdk-version 35 --version-code 1 --version-name 1.0
"$BT/zipalign" -f 4 "$TMP/unsigned.apk" "$TMP/aligned.apk"
"$BT/apksigner" sign --ks ../../android/anchor.jks --ks-pass pass:anchorpass --out dummy.apk "$TMP/aligned.apk"
rm -rf "$TMP" dummy.apk.idsig
