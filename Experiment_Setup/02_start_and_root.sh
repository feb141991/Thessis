#!/usr/bin/env bash
# Boots ForensicsAVD and confirms `adb root` works, per Methodology 3.3/3.6.
# Full-filesystem access (RQ3) depends on root actually being granted here.
set -euo pipefail

AVD_NAME="${AVD_NAME:-ForensicsAVD}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-180}"

if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
  echo "ERROR: Set ANDROID_HOME (or ANDROID_SDK_ROOT) to your Android SDK path." >&2
  exit 1
fi

command -v emulator >/dev/null || { echo "ERROR: emulator not on PATH." >&2; exit 1; }
command -v adb >/dev/null || { echo "ERROR: adb not on PATH." >&2; exit 1; }

echo "== Starting ${AVD_NAME} =="
emulator -avd "${AVD_NAME}" -writable-system -no-snapshot-save -no-audio &
EMULATOR_PID=$!

echo "== Waiting for device =="
adb wait-for-device

echo "== Waiting for boot to complete (timeout ${BOOT_TIMEOUT}s) =="
elapsed=0
until [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; do
  if (( elapsed >= BOOT_TIMEOUT )); then
    echo "ERROR: Boot did not complete within ${BOOT_TIMEOUT}s." >&2
    exit 1
  fi
  sleep 3
  elapsed=$((elapsed + 3))
done
echo "Boot completed after ~${elapsed}s."

echo "== Requesting root =="
adb root
sleep 2
adb wait-for-device

UID_CHECK="$(adb shell id -u 2>/dev/null | tr -d '\r')"
if [[ "${UID_CHECK}" != "0" ]]; then
  echo "ERROR: adb root did not grant uid 0 (got '${UID_CHECK}'). Confirm the AVD uses a google_apis (not google_apis_playstore) image." >&2
  exit 1
fi

echo "== Remounting system as read-write (optional, full-filesystem access) =="
adb remount || echo "WARNING: adb remount failed; ADB-only access may still be sufficient for RQ3's baseline comparison."

echo "== adb root confirmed: shell is running as uid 0 =="
echo "Emulator PID: ${EMULATOR_PID} (leave running for the current test phase)"
echo "Next: run ./03_install_wallets.sh"
