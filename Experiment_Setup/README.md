# Experiment Setup

Everything needed to run the A0–A12 experiment from Methodology 3.4.

**These scripts run on your own machine.** They need the Android SDK, hardware
virtualisation (KVM or macOS Hypervisor), and a display — none of which exist
in a Claude session, so nothing here can be executed for you.

## Before you start

Ethics first: per Methodology 3.10, CURES approval must be confirmed as
covering the **data-collection** stage before running any phase beyond setup.
Setting up the emulator is fine; creating wallets and taking captures is not,
until that is settled.

## Run order

```bash
./00_check_prereqs.sh          # reports what's missing, changes nothing
./01_setup_emulator.sh         # creates the rooted ForensicsAVD
./02_start_and_root.sh         # boots it, confirms adb root
# put the three APKs in ./apks/ first — see README_APK_SOURCES.txt
./03_install_wallets.sh        # sideloads them, logs sha256 per install
```

Then, for each wallet, walk the 13 phases. Capture **before** the first action
(A0 is the clean baseline), then after each action:

```bash
./04_capture.py capture --app metamask --phase A0
#   ... install the app on the device ...
./04_capture.py capture --app metamask --phase A1
./04_capture.py diff    --app metamask --phase A1
#   ... create the wallet ...
./04_capture.py capture --app metamask --phase A2
./04_capture.py diff    --app metamask --phase A2
#   ... and so on through A12 ...
./04_capture.py report  --app metamask
```

Repeat for `trustwallet` and `bluewallet`. Run the pilot (3.5) on one wallet
end to end first, before committing to all three.

## The phases (3.4)

| Phase | Action on the device |
|-------|----------------------|
| A0  | Nothing — clean baseline, app not yet installed |
| A1  | Install the app, no account created |
| A2  | Create a new test wallet, set PIN/biometric if offered |
| A3  | Import a test seed phrase |
| A4  | Receive a test-network transaction |
| A5  | Send a test-network transaction |
| A6  | Add a custom token/network, or connect to a test dApp |
| A7  | Log out, lock the wallet, close the app |
| A8  | Delete the wallet using the app's own option |
| A9  | Clear the app's cache from Android settings |
| A10 | Clear the app's storage from Android settings |
| A11 | Uninstall, then reinstall |
| A12 | Android backup and restore |

## What each file does

- `00_check_prereqs.sh` — verifies SDK, virtualisation, Python, APKs, disk.
- `01_setup_emulator.sh` — creates `ForensicsAVD` on a Google APIs (not Google
  Play) image, which is what makes `adb root` possible (3.3).
- `02_start_and_root.sh` — boots the AVD, waits for boot, confirms uid 0.
- `03_install_wallets.sh` — sideloads the APKs, logs a sha256 per install.
- `04_capture.py` — the capture/diff/report tool described in 3.6.
- `README_APK_SOURCES.txt` — how to obtain each APK defensibly.

## What `04_capture.py` produces

Under `./captures/<app>/<phase>/`:

- `capture.json` — every file path with sha256, size, timestamps, and a
  storage category from the taxonomy in 3.7; plus package version and install
  times, and a `capture_sha256` anchoring the snapshot itself.
- `dumpsys_package.txt` — raw package state at that phase.
- `files/` — the pulled files themselves (skip with `--no-pull`).
- `diff.json` / `diff.txt` — what changed versus A0 and versus the previous
  phase: added, removed, modified, with hashes.

And per app:

- `persistence_matrix.csv` — one row per artefact, columns for presence at
  every phase, plus first seen, last seen, and a suggested status. This is the
  table Chapters 5 and 6 are built from.
- `capture_custody_log.csv` — one row per capture: who, when, how many files,
  package version, capture hash, device fingerprint.

`suggested_status` reports observed presence only. It is a starting point to
confirm, not a finding — deciding whether deleted content is *recoverable*
still needs the WAL/cache examination described in 3.7.

## Notes

- `capture` needs the device attached and rooted; `diff` and `report` work
  offline, so you can re-analyse without re-running the experiment.
- Captures are additive and phase-named, so an interrupted run can be resumed.
  `report` tells you which phases are still missing.
- Record the exact Android version, AVD config, and app versions — they are
  part of the result (3.11), and `capture.json` stores them for you.
