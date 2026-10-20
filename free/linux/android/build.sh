#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")"

SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
BT="$SDK/build-tools/$(ls "$SDK/build-tools" | sort -V | tail -1)"
PLATFORM="$SDK/platforms/$(ls "$SDK/platforms" | sort -V | tail -1)/android.jar"
VERSION_CODE=$(grep -oP 'VERSION = \K[0-9]+' src/app/anchor/agent/CommandProvider.java)
OUT=../desktop/anchor-agent.apk

KEYSTORE=anchor.jks
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -keystore "$KEYSTORE" -storepass anchorpass -keypass anchorpass \
    -alias anchor -keyalg RSA -keysize 3072 -validity 36500 -dname "CN=Anchor" >/dev/null
fi

rm -rf build && mkdir -p build/classes build/dex
"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -I "$PLATFORM" --manifest AndroidManifest.xml -o build/base.apk build/res.zip \
  --min-sdk-version 29 --target-sdk-version 35 \
  --version-code "$VERSION_CODE" --version-name "1.0.$VERSION_CODE"
javac -nowarn -Xlint:-options -source 1.8 -target 1.8 -bootclasspath "$PLATFORM" \
  -d build/classes $(find src -name '*.java')
"$BT/d8" --release --min-api 29 --lib "$PLATFORM" --output build/dex $(find build/classes -name '*.class')
cp build/base.apk build/unsigned.apk
(cd build/dex && zip -q ../unsigned.apk classes.dex)
"$BT/zipalign" -f 4 build/unsigned.apk build/aligned.apk
"$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:anchorpass --out "$OUT" build/aligned.apk
rm -f "$OUT.idsig"

"$BT/aapt2" link -I "$PLATFORM" --manifest placeholder/AndroidManifest.xml -o build/placeholder.apk \
  --min-sdk-version 24 --target-sdk-version 28 --version-code 1 --version-name 1
unzip -p build/placeholder.apk AndroidManifest.xml > ../desktop/placeholder-manifest.bin
echo "Built $(realpath "$OUT") (version $VERSION_CODE)"
