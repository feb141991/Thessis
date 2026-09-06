#!/usr/bin/env bash
# Checks that this machine can actually run the experiment before you start.
# Run this FIRST. It changes nothing — it only reports what is missing.
set -uo pipefail

ok=0
fail=0
warn=0

pass() { echo "  [ OK ]   $1"; ok=$((ok + 1)); }
bad()  { echo "  [FAIL]   $1"; fail=$((fail + 1)); }
soft() { echo "  [WARN]   $1"; warn=$((warn + 1)); }

echo "== Host =="
echo "  $(uname -srm)"

echo
echo "== Hardware virtualisation (required by the Android emulator) =="
case "$(uname -s)" in
  Linux)
    if [[ -e /dev/kvm ]]; then
      if [[ -r /dev/kvm && -w /dev/kvm ]]; then
        pass "/dev/kvm present and accessible"
      else
        bad "/dev/kvm exists but is not accessible by this user — add yourself to the 'kvm' group and re-login"
      fi
    else
      bad "/dev/kvm not present — the x86_64 emulator cannot run. Enable VT-x/AMD-V in BIOS, or run on a machine that supports it."
    fi
    ;;
  Darwin)
    pass "macOS — the emulator uses the Hypervisor framework (no /dev/kvm needed)"
    ;;
  *)
    soft "Unrecognised OS; verify emulator acceleration manually with: emulator -accel-check"
    ;;
esac

echo
echo "== Android SDK =="
if [[ -n "${ANDROID_HOME:-}" || -n "${ANDROID_SDK_ROOT:-}" ]]; then
  pass "ANDROID_HOME/ANDROID_SDK_ROOT set (${ANDROID_HOME:-$ANDROID_SDK_ROOT})"
else
  bad "Neither ANDROID_HOME nor ANDROID_SDK_ROOT is set"
fi

for tool in sdkmanager avdmanager adb emulator; do
  if command -v "$tool" >/dev/null 2>&1; then
    pass "$tool on PATH ($(command -v "$tool"))"
  else
    bad "$tool not on PATH"
  fi
done

if command -v java >/dev/null 2>&1; then
  pass "java present ($(java -version 2>&1 | grep -i 'version' | head -1))"
else
  bad "java not on PATH (required by sdkmanager/avdmanager)"
fi

echo
echo "== Capture tooling =="
if command -v python3 >/dev/null 2>&1; then
  pyver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
    pass "python3 ${pyver}"
  else
    bad "python3 ${pyver} is too old — 04_capture.py needs 3.8+"
  fi
else
  bad "python3 not on PATH — required by 04_capture.py"
fi

command -v sha256sum >/dev/null 2>&1 && pass "sha256sum present" \
  || { command -v shasum >/dev/null 2>&1 && soft "sha256sum missing but shasum present — 03_install_wallets.sh expects sha256sum (on macOS: brew install coreutils)" \
       || bad "no sha256sum available — needed for chain-of-custody hashing"; }

echo
echo "== Wallet APKs =="
APKS_DIR="${APKS_DIR:-./apks}"
for apk in bluewallet.apk metamask.apk trustwallet.apk; do
  if [[ -f "${APKS_DIR}/${apk}" ]]; then
    pass "${APKS_DIR}/${apk} present"
  else
    soft "${APKS_DIR}/${apk} missing — see README_APK_SOURCES.txt"
  fi
done

echo
echo "== Disk space =="
avail_kb="$(df -Pk . | awk 'NR==2 {print $4}')"
avail_gb=$((avail_kb / 1024 / 1024))
if (( avail_gb >= 30 )); then
  pass "${avail_gb} GB free (system image + AVD + 39 captures)"
else
  soft "${avail_gb} GB free — allow ~30 GB for the system image, AVD, and captures"
fi

echo
echo "== Summary =="
echo "  ${ok} passed, ${warn} warnings, ${fail} failures"
if (( fail > 0 )); then
  echo
  echo "Fix the failures above before running 01_setup_emulator.sh."
  exit 1
fi
echo
echo "Ready. Next: ./01_setup_emulator.sh"
