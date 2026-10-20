#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
ADB="$(command -v adb || echo "$SDK/platform-tools/adb")"

run_java_tests() {
  if command -v javac >/dev/null; then
    local out; out=$(mktemp -d)
    javac -nowarn -d "$out" android/src/app/anchor/agent/Timing.java android/test/TimingTest.java
    java -cp "$out" app.anchor.agent.TimingTest | tail -1
    rm -rf "$out"
  else
    echo "Skipping Java tests (no JDK)"
  fi
}

if [ "${1:-}" != "--device" ]; then
  run_java_tests
  exec python3 -m unittest discover -s tests -p "test_*.py" "$@"
fi
run_java_tests

[ -f desktop/anchor-agent.apk ] || ./android/build.sh
[ -f tests/fixtures/dummy.apk ] || tests/fixtures/build_dummy.sh

EMU_PID=""
if [ -z "${ANCHOR_TEST_SERIAL:-}" ]; then
  AVD="${ANCHOR_TEST_AVD:-anchor_test}"
  PORT=5584
  echo "Booting emulator $AVD (wiped) on port $PORT…"
  "$SDK/emulator/emulator" -avd "$AVD" -port "$PORT" -wipe-data -no-window -no-audio -no-snapshot \
    -no-boot-anim -memory 2048 >/tmp/anchor-test-emulator.log 2>&1 &
  EMU_PID=$!
  export ANCHOR_TEST_SERIAL="emulator-$PORT"
  trap '"$ADB" -s "$ANCHOR_TEST_SERIAL" emu kill >/dev/null 2>&1 || kill $EMU_PID 2>/dev/null || true' EXIT
  timeout 300 "$ADB" -s "$ANCHOR_TEST_SERIAL" wait-for-device shell \
    'while [ "$(getprop sys.boot_completed)" != 1 ]; do sleep 2; done'
fi

python3 -m unittest discover -s tests -p "test_*.py" -v
