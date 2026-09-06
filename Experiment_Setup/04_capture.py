#!/usr/bin/env python3
"""
Forensic capture, diff, and persistence-report tool for the wallet artefact
experiment (Methodology 3.4, 3.6, 3.7).

Three subcommands:

  capture   Record the state of one app's storage at one phase: every file
            path, its sha256, size, and timestamps, plus package metadata.
            Optionally pulls the files themselves for later examination.

  diff      Compare one phase's capture against the A0 baseline and against
            the phase immediately before it, and write the change log.

  report    Build the persistence matrix across all captured phases: when
            each artefact first appeared, whether it survived deletion,
            clearing, and uninstall, as CSV for the thesis tables.

`capture` needs a rooted device attached (see 02_start_and_root.sh).
`diff` and `report` work offline on saved captures.

Typical use, once per phase:

    ./04_capture.py capture --app metamask --phase A0
    ... perform the phase A1 action on the device ...
    ./04_capture.py capture --app metamask --phase A1
    ./04_capture.py diff    --app metamask --phase A1
    ...
    ./04_capture.py report  --app metamask
"""

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

# Methodology 3.4 — the 13 phases, in order.
PHASES = [
    ("A0", "baseline"),
    ("A1", "install"),
    ("A2", "create_wallet"),
    ("A3", "import_wallet"),
    ("A4", "receive_transaction"),
    ("A5", "send_transaction"),
    ("A6", "add_token_or_network"),
    ("A7", "lock_or_logout"),
    ("A8", "delete_wallet"),
    ("A9", "clear_cache"),
    ("A10", "clear_storage"),
    ("A11", "uninstall_reinstall"),
    ("A12", "backup_restore"),
]
PHASE_ORDER = [p for p, _ in PHASES]
PHASE_LABELS = dict(PHASES)

# Phases that attempt to remove data — used to derive persistence (3.7).
REMOVAL_PHASES = ["A8", "A9", "A10", "A11"]

# Methodology 3.2 — the three wallets under test.
APPS = {
    "metamask": "io.metamask",
    "trustwallet": "com.wallet.crypto.trustapp",
    "bluewallet": "io.bluewallet.bluewallet",
}

# Storage categories from the artefact taxonomy (3.7). First match wins, so
# the more specific patterns are listed before the general ones.
CATEGORY_RULES = [
    (re.compile(r"/shared_prefs/"), "shared_preferences"),
    (re.compile(r"\.db-wal$|\.sqlite-wal$|-wal$"), "sqlite_wal"),
    (re.compile(r"\.db-shm$|\.sqlite-shm$|-shm$"), "sqlite_shm"),
    (re.compile(r"/databases/|\.db$|\.sqlite3?$"), "sqlite_database"),
    (re.compile(r"/app_webview/|/app_WebView/"), "webview_storage"),
    (re.compile(r"/cache/|/code_cache/"), "cache"),
    (re.compile(r"/no_backup/"), "protected_no_backup"),
    (re.compile(r"^/data/misc/keystore/"), "keystore_reference"),
    (re.compile(r"^/data/app/"), "apk_package"),
    (re.compile(r"^/sdcard/|^/storage/emulated/0/"), "external_storage"),
    (re.compile(r"/files/"), "app_local_files"),
]


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def categorise(path):
    for pattern, name in CATEGORY_RULES:
        if pattern.search(path):
            return name
    return "other"


# --------------------------------------------------------------------------
# adb helpers
# --------------------------------------------------------------------------

class AdbError(RuntimeError):
    pass


class Adb:
    def __init__(self, serial=None):
        self.serial = serial

    def _base(self):
        return ["adb"] + (["-s", self.serial] if self.serial else [])

    def run(self, *args, check=True):
        proc = subprocess.run(
            self._base() + list(args),
            capture_output=True,
            text=True,
            errors="replace",
        )
        if check and proc.returncode != 0:
            raise AdbError(
                "adb %s failed (%d): %s"
                % (" ".join(args), proc.returncode, proc.stderr.strip())
            )
        return proc.stdout.replace("\r\n", "\n")

    def shell(self, command, check=True):
        return self.run("shell", command, check=check)

    def require_device(self):
        try:
            state = self.run("get-state").strip()
        except AdbError as exc:
            raise AdbError(
                "No device attached. Run ./02_start_and_root.sh first."
            ) from exc
        if state != "device":
            raise AdbError("Device is in state '%s', expected 'device'." % state)

    def require_root(self):
        uid = self.shell("id -u").strip() or "?"
        if uid != "0":
            raise AdbError(
                "adb shell is running as uid %s, not 0. Full-filesystem capture "
                "needs root — run ./02_start_and_root.sh, and confirm the AVD "
                "uses a google_apis (not google_apis_playstore) image." % uid
            )

    def device_info(self):
        def prop(name):
            return self.shell("getprop %s" % name, check=False).strip()

        return {
            "serial": self.serial or self.run("get-serialno").strip(),
            "android_release": prop("ro.build.version.release"),
            "sdk_int": prop("ro.build.version.sdk"),
            "build_fingerprint": prop("ro.build.fingerprint"),
            "product_model": prop("ro.product.model"),
        }


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------

def storage_roots(package):
    """Every location the taxonomy in 3.7 expects artefacts to live in."""
    return [
        "/data/data/%s" % package,
        "/data/app/%s" % package,
        "/sdcard/Android/data/%s" % package,
        "/sdcard/Download",
        "/sdcard/Pictures/Screenshots",
        "/sdcard/DCIM/Screenshots",
        "/data/misc/keystore",
    ]


def list_hashes(adb, root):
    """path -> sha256 for every regular file under root."""
    out = adb.shell(
        "[ -e '%s' ] && find '%s' -type f -exec sha256sum {} + 2>/dev/null" % (root, root),
        check=False,
    )
    results = {}
    for line in out.splitlines():
        line = line.rstrip("\n")
        if not line or "  " not in line:
            continue
        digest, path = line.split("  ", 1)
        digest = digest.strip()
        if len(digest) == 64:
            results[path.strip()] = digest
    return results


def list_stats(adb, root):
    """path -> (size, mtime, ctime) for every regular file under root."""
    out = adb.shell(
        "[ -e '%s' ] && find '%s' -type f -exec stat -c '%%s|%%Y|%%Z|%%n' {} + 2>/dev/null"
        % (root, root),
        check=False,
    )
    results = {}
    for line in out.splitlines():
        parts = line.rstrip("\n").split("|", 3)
        if len(parts) != 4:
            continue
        size, mtime, ctime, path = parts
        try:
            results[path.strip()] = (int(size), int(mtime), int(ctime))
        except ValueError:
            continue
    return results


def package_info(adb, package):
    raw = adb.shell("dumpsys package %s" % package, check=False)
    installed = bool(re.search(r"^\s*Package \[%s\]" % re.escape(package), raw, re.M))

    def field(pattern):
        match = re.search(pattern, raw)
        return match.group(1).strip() if match else None

    return {
        "installed": installed,
        "version_name": field(r"versionName=(\S+)"),
        "version_code": field(r"versionCode=(\d+)"),
        "first_install_time": field(r"firstInstallTime=(.+)"),
        "last_update_time": field(r"lastUpdateTime=(.+)"),
        "raw_dumpsys": raw,
    }


def files_digest(files):
    """A single hash over the whole file map, anchoring the capture itself."""
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cmd_capture(args):
    adb = Adb(args.serial)
    adb.require_device()
    adb.require_root()

    package = APPS[args.app]
    phase = args.phase
    evidence_dir = Path(args.out) / args.app / phase
    evidence_dir.mkdir(parents=True, exist_ok=True)

    print("== Capturing %s (%s) at phase %s: %s ==" % (args.app, package, phase, PHASE_LABELS[phase]))

    files = {}
    for root in storage_roots(package):
        hashes = list_hashes(adb, root)
        stats = list_stats(adb, root)
        for path, digest in hashes.items():
            if path in files:
                # Roots can alias one another (/sdcard vs /storage/emulated/0).
                continue
            size, mtime, ctime = stats.get(path, (None, None, None))
            files[path] = {
                "sha256": digest,
                "size": size,
                "mtime": mtime,
                "ctime": ctime,
                "category": categorise(path),
            }

    pkg = package_info(adb, package)
    raw_dumpsys = pkg.pop("raw_dumpsys")
    (evidence_dir / "dumpsys_package.txt").write_text(raw_dumpsys, encoding="utf-8")

    snapshot = {
        "schema": SCHEMA_VERSION,
        "app": args.app,
        "package": package,
        "phase": phase,
        "phase_label": PHASE_LABELS[phase],
        "captured_utc": utc_now(),
        "operator": args.operator or os.environ.get("USER") or "unknown",
        "device": adb.device_info(),
        "package_info": pkg,
        "roots": storage_roots(package),
        "file_count": len(files),
        "files": files,
    }
    snapshot["capture_sha256"] = files_digest(files)

    snapshot_path = evidence_dir / "capture.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    if args.pull:
        pulled_dir = evidence_dir / "files"
        pulled = 0
        for path in files:
            target = pulled_dir / path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                adb.run("pull", path, str(target))
                pulled += 1
            except AdbError as exc:
                print("  WARNING: could not pull %s (%s)" % (path, exc))
        print("  pulled %d/%d files into %s" % (pulled, len(files), pulled_dir))

    append_custody_log(Path(args.out), snapshot)

    print("  %d files recorded" % len(files))
    print("  package installed: %s (version %s)" % (pkg["installed"], pkg["version_name"]))
    print("  capture sha256: %s" % snapshot["capture_sha256"])
    print("  written to %s" % snapshot_path)
    return 0


def append_custody_log(out_dir, snapshot):
    log_path = out_dir / "capture_custody_log.csv"
    new = not log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(
                [
                    "captured_utc",
                    "operator",
                    "app",
                    "package",
                    "phase",
                    "phase_label",
                    "file_count",
                    "package_installed",
                    "package_version",
                    "capture_sha256",
                    "device_fingerprint",
                ]
            )
        writer.writerow(
            [
                snapshot["captured_utc"],
                snapshot["operator"],
                snapshot["app"],
                snapshot["package"],
                snapshot["phase"],
                snapshot["phase_label"],
                snapshot["file_count"],
                snapshot["package_info"]["installed"],
                snapshot["package_info"]["version_name"],
                snapshot["capture_sha256"],
                snapshot["device"].get("build_fingerprint"),
            ]
        )


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------

def load_capture(out_dir, app, phase):
    path = Path(out_dir) / app / phase / "capture.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare(before, after):
    """Change set between two capture file maps."""
    before_files = before["files"]
    after_files = after["files"]
    before_paths = set(before_files)
    after_paths = set(after_files)

    added = [
        {"path": p, "sha256": after_files[p]["sha256"], "category": after_files[p]["category"]}
        for p in sorted(after_paths - before_paths)
    ]
    removed = [
        {"path": p, "sha256": before_files[p]["sha256"], "category": before_files[p]["category"]}
        for p in sorted(before_paths - after_paths)
    ]
    modified = []
    unchanged = 0
    for p in sorted(before_paths & after_paths):
        if before_files[p]["sha256"] != after_files[p]["sha256"]:
            modified.append(
                {
                    "path": p,
                    "category": after_files[p]["category"],
                    "sha256_before": before_files[p]["sha256"],
                    "sha256_after": after_files[p]["sha256"],
                    "size_before": before_files[p]["size"],
                    "size_after": after_files[p]["size"],
                }
            )
        else:
            unchanged += 1

    return {
        "from_phase": before["phase"],
        "to_phase": after["phase"],
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged_count": unchanged,
    }


def summarise(change):
    lines = [
        "%s (%s) -> %s (%s)"
        % (
            change["from_phase"],
            PHASE_LABELS.get(change["from_phase"], "?"),
            change["to_phase"],
            PHASE_LABELS.get(change["to_phase"], "?"),
        ),
        "  added:     %d" % len(change["added"]),
        "  removed:   %d" % len(change["removed"]),
        "  modified:  %d" % len(change["modified"]),
        "  unchanged: %d" % change["unchanged_count"],
    ]
    for heading, key in (("Added", "added"), ("Removed", "removed"), ("Modified", "modified")):
        if not change[key]:
            continue
        lines.append("")
        lines.append("%s:" % heading)
        for entry in change[key]:
            lines.append("  [%s] %s" % (entry["category"], entry["path"]))
    return "\n".join(lines)


def cmd_diff(args):
    phase = args.phase
    current = load_capture(args.out, args.app, phase)
    if current is None:
        print("ERROR: no capture for %s at %s — run `capture` first." % (args.app, phase), file=sys.stderr)
        return 1

    comparisons = {}

    baseline = load_capture(args.out, args.app, "A0")
    if baseline is not None and phase != "A0":
        comparisons["vs_baseline"] = compare(baseline, current)
    elif phase != "A0":
        print("WARNING: no A0 baseline capture found; skipping baseline comparison.")

    index = PHASE_ORDER.index(phase)
    previous = None
    for candidate in reversed(PHASE_ORDER[:index]):
        previous = load_capture(args.out, args.app, candidate)
        if previous is not None:
            break
    if previous is not None:
        comparisons["vs_previous"] = compare(previous, current)
    elif phase != "A0":
        print("WARNING: no earlier capture found; skipping previous-phase comparison.")

    diff_dir = Path(args.out) / args.app / phase
    diff_dir.mkdir(parents=True, exist_ok=True)
    (diff_dir / "diff.json").write_text(
        json.dumps(comparisons, indent=2, sort_keys=True), encoding="utf-8"
    )

    text = ["Change log for %s at %s (%s)" % (args.app, phase, PHASE_LABELS[phase]), ""]
    for key, change in comparisons.items():
        text.append("== %s ==" % key.replace("_", " "))
        text.append(summarise(change))
        text.append("")
    report = "\n".join(text)
    (diff_dir / "diff.txt").write_text(report, encoding="utf-8")
    print(report)
    print("Written to %s" % (diff_dir / "diff.txt"))
    return 0


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def suggested_status(present_at, captured_phases):
    """
    Derive a first-pass persistence status from observed presence alone.

    This is a starting point for the researcher to confirm, not a finding in
    itself: it reports what the captures show, and deliberately does not try
    to judge recoverability of deleted content, which needs the WAL/cache
    examination described in 3.7.
    """
    seen = [p for p in captured_phases if present_at.get(p)]
    if not seen:
        return "not_recoverable"

    removals_captured = [p for p in REMOVAL_PHASES if p in captured_phases]
    survived = [p for p in removals_captured if present_at.get(p)]

    if not removals_captured:
        return "active"
    if "A11" in survived:
        return "persistent_after_uninstall"
    if "A10" in survived:
        return "persistent_after_clear_storage"
    if survived:
        return "persistent_after_deletion"
    return "active"


def cmd_report(args):
    app_dir = Path(args.out) / args.app
    captures = {}
    for phase in PHASE_ORDER:
        snapshot = load_capture(args.out, args.app, phase)
        if snapshot is not None:
            captures[phase] = snapshot

    if not captures:
        print("ERROR: no captures found under %s" % app_dir, file=sys.stderr)
        return 1

    captured_phases = [p for p in PHASE_ORDER if p in captures]
    print("Captures found: %s" % ", ".join(captured_phases))
    missing = [p for p in PHASE_ORDER if p not in captures]
    if missing:
        print("Not yet captured: %s" % ", ".join(missing))

    all_paths = {}
    for phase in captured_phases:
        for path, meta in captures[phase]["files"].items():
            all_paths.setdefault(path, meta["category"])

    rows = []
    for path in sorted(all_paths):
        present_at = {p: path in captures[p]["files"] for p in captured_phases}
        seen = [p for p in captured_phases if present_at[p]]
        hashes = {
            captures[p]["files"][path]["sha256"] for p in seen
        }
        row = {
            "path": path,
            "category": all_paths[path],
            "first_seen": seen[0] if seen else "",
            "last_seen": seen[-1] if seen else "",
            "distinct_hashes": len(hashes),
            "suggested_status": suggested_status(present_at, captured_phases),
        }
        for phase in PHASE_ORDER:
            row["present_%s" % phase] = (
                "" if phase not in captures else ("yes" if present_at[phase] else "no")
            )
        rows.append(row)

    columns = (
        ["path", "category", "first_seen", "last_seen", "distinct_hashes"]
        + ["present_%s" % p for p in PHASE_ORDER]
        + ["suggested_status"]
    )
    csv_path = app_dir / "persistence_matrix.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    by_status = {}
    for row in rows:
        by_status.setdefault(row["suggested_status"], 0)
        by_status[row["suggested_status"]] += 1
    by_category = {}
    for row in rows:
        by_category.setdefault(row["category"], 0)
        by_category[row["category"]] += 1

    print()
    print("%d distinct artefact paths across %d phases" % (len(rows), len(captured_phases)))
    print()
    print("By suggested status:")
    for status, count in sorted(by_status.items(), key=lambda kv: -kv[1]):
        print("  %-34s %d" % (status, count))
    print()
    print("By storage category:")
    for category, count in sorted(by_category.items(), key=lambda kv: -kv[1]):
        print("  %-34s %d" % (category, count))
    print()
    print("Written to %s" % csv_path)
    print()
    print("Note: suggested_status reflects observed presence only. Confirm each")
    print("before reporting it — recoverability of deleted content still needs")
    print("the WAL/cache examination described in Methodology 3.7.")
    return 0


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Forensic capture/diff/report tool for the wallet artefact experiment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out",
        default="./captures",
        help="directory holding captures and reports (default: ./captures)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_capture = sub.add_parser("capture", help="record one app's storage state at one phase")
    p_capture.add_argument("--app", required=True, choices=sorted(APPS))
    p_capture.add_argument("--phase", required=True, choices=PHASE_ORDER)
    p_capture.add_argument("--serial", help="adb device serial, if more than one is attached")
    p_capture.add_argument("--operator", help="who ran this capture (for the custody log)")
    p_capture.add_argument(
        "--no-pull",
        dest="pull",
        action="store_false",
        help="record hashes and metadata only, do not copy the files off the device",
    )
    p_capture.set_defaults(pull=True, func=cmd_capture)

    p_diff = sub.add_parser("diff", help="compare a phase against baseline and previous phase")
    p_diff.add_argument("--app", required=True, choices=sorted(APPS))
    p_diff.add_argument("--phase", required=True, choices=PHASE_ORDER)
    p_diff.set_defaults(func=cmd_diff)

    p_report = sub.add_parser("report", help="build the persistence matrix across all phases")
    p_report.add_argument("--app", required=True, choices=sorted(APPS))
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    try:
        return args.func(args)
    except AdbError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
