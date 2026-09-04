#!/usr/bin/env bash
# Sideloads the three wallet APKs from ./apks/ onto ForensicsAVD and logs
# sha256 hashes + install results for chain of custody (Methodology 3.6/3.9).
# See README_APK_SOURCES.txt for how to legitimately obtain each APK first.
set -euo pipefail

APKS_DIR="${APKS_DIR:-./apks}"
LOG_DIR="${LOG_DIR:-./logs}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/chain_of_custody_$(date -u +%Y%m%dT%H%M%SZ).csv}"

# package_name is what we verify against `adb shell pm list packages` after
# install; filename is what must exist under APKS_DIR (see README for how
# multi-APK bundles pulled from a Play Store device should be named/merged).
declare -A WALLETS=(
  ["bluewallet.apk"]="io.bluewallet.bluewallet"
  ["metamask.apk"]="io.metamask"
  ["trustwallet.apk"]="com.wallet.crypto.trustapp"
)

command -v adb >/dev/null || { echo "ERROR: adb not on PATH." >&2; exit 1; }
command -v sha256sum >/dev/null || { echo "ERROR: sha256sum not available." >&2; exit 1; }

adb get-state >/dev/null 2>&1 || {
  echo "ERROR: no device attached. Run ./02_start_and_root.sh first." >&2
  exit 1
}

mkdir -p "${LOG_DIR}"
echo "timestamp_utc,filename,package,sha256,install_result" > "${LOG_FILE}"

for apk in "${!WALLETS[@]}"; do
  path="${APKS_DIR}/${apk}"
  package="${WALLETS[$apk]}"

  if [[ ! -f "${path}" ]]; then
    echo "ERROR: ${path} not found. See README_APK_SOURCES.txt." >&2
    exit 1
  fi

  hash="$(sha256sum "${path}" | awk '{print $1}')"
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  echo "== Installing ${apk} (${package}) =="
  if adb install -r "${path}"; then
    result="success"
  else
    result="failed"
  fi

  if adb shell pm list packages | tr -d '\r' | grep -qx "package:${package}"; then
    verify="verified_on_device"
  else
    verify="not_found_on_device"
  fi

  echo "${ts},${apk},${package},${hash},${result}:${verify}" >> "${LOG_FILE}"
  echo "  sha256: ${hash}"
  echo "  result: ${result} (${verify})"
done

echo "== Done =="
echo "Chain-of-custody log written to ${LOG_FILE}"
