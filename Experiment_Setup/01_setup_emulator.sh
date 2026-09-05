#!/usr/bin/env bash
# Creates the rooted, Google APIs (not Google Play) AVD used for all testing,
# per Methodology 3.3 (Test Device). Google APIs images ship with a root
# adbd; Google Play images do not and cannot be rooted through adb alone.
set -euo pipefail

AVD_NAME="${AVD_NAME:-ForensicsAVD}"
API_LEVEL="${API_LEVEL:-33}"
ARCH="${ARCH:-x86_64}"
DEVICE_PROFILE="${DEVICE_PROFILE:-pixel_6}"
SYSTEM_IMAGE="system-images;android-${API_LEVEL};google_apis;${ARCH}"

if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
  echo "ERROR: Set ANDROID_HOME (or ANDROID_SDK_ROOT) to your Android SDK path." >&2
  exit 1
fi
SDK_ROOT="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"

command -v sdkmanager >/dev/null || {
  echo "ERROR: sdkmanager not on PATH. Add \$SDK_ROOT/cmdline-tools/latest/bin to PATH." >&2
  exit 1
}
command -v avdmanager >/dev/null || {
  echo "ERROR: avdmanager not on PATH. Add \$SDK_ROOT/cmdline-tools/latest/bin to PATH." >&2
  exit 1
}

echo "== Installing required SDK packages =="
yes | sdkmanager --licenses >/dev/null || true
sdkmanager --install \
  "platform-tools" \
  "emulator" \
  "platforms;android-${API_LEVEL}" \
  "${SYSTEM_IMAGE}"

if avdmanager list avd | grep -qx "    Name: ${AVD_NAME}"; then
  echo "AVD '${AVD_NAME}' already exists, skipping creation."
else
  echo "== Creating AVD: ${AVD_NAME} (${SYSTEM_IMAGE}) =="
  echo "no" | avdmanager create avd \
    --name "${AVD_NAME}" \
    --package "${SYSTEM_IMAGE}" \
    --device "${DEVICE_PROFILE}" \
    --force
fi

echo "== Done =="
echo "AVD '${AVD_NAME}' is ready (image: ${SYSTEM_IMAGE})."
echo "Next: run ./02_start_and_root.sh"
