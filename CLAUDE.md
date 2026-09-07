# Project context

MSc Digital Forensics thesis, Cranfield University — *Forensic Artefact
Analysis of Cryptocurrency Wallet Applications on Android: Recovery,
Persistence, and Evidential Value*.

Controlled experiment: three Android wallet apps are each taken through a
fixed 13-step sequence on a rooted emulator, with a forensic capture after
every step, to establish what artefacts appear, which survive attempts to
remove them, and how much each is actually worth as evidence.

Research questions:

- **RQ1** — What artefacts do the apps leave during install, wallet
  creation/import, use, logout, deletion, and uninstall?
- **RQ2** — Which survive cache clearing, wallet deletion, storage clearing,
  uninstall/reinstall, and backup/restore?
- **RQ3** — How does acquisition method (ADB vs. rooted full-filesystem, vs.
  a commercial tool if the university provides one) affect recovery?
- **RQ4** — How much do recovered artefacts actually prove about who used the
  wallet, when, and what they did?

## Repository layout

```
Thesis.pdf                 compiled thesis (LaTeX, Cranfield CUThesisTemplate2026, APA7)
Thesis_Draft.docx          same content, plain-language working draft
Progress_Summaries/        dated status/risk snapshots
Experiment_Setup/          the experiment toolchain — see its README.md
```

Note: the **LaTeX source is not in this repo**, only the compiled PDF. If the
`.tex` sources are available locally they should be added, so the thesis is
version-controlled alongside the tooling.

## Hard constraints

**Ethics is a gate, not a formality.** CURES approval currently covers the
setup stage (building the emulator, preparing the environment). It must be
confirmed as covering the **data-collection** stage before any wallet is
created, any transaction sent, or any capture taken — i.e. before phase A2
onward. The module rules state the thesis cannot be marked without confirmed
approval on file. Do not help start data collection before this is settled;
flag it if the question comes up.

**Never fabricate a citation.** Chapter 2 was deliberately left thin rather
than padded with invented sources — every reference in it is real and
checkable at the URL given. Never add a source that has not actually been
read, and never invent a plausible-looking one.

**Don't overclaim what evidence proves.** The thesis draws a hard line
between "this device, app, and wallet address are connected" and "this person
controlled that wallet." The second needs corroboration beyond the device.
Analysis and write-up should preserve that distinction.

**Results are version-specific.** Wallet apps change storage behaviour between
releases, so record exact app versions, Android version, and AVD config with
every run (3.11). `04_capture.py` records these automatically.

## The experiment

Three apps, chosen to cover different chain models (3.2):

| App | Package | Represents |
|-----|---------|-----------|
| MetaMask | `io.metamask` | EVM/Ethereum |
| Trust Wallet | `com.wallet.crypto.trustapp` | multi-chain |
| BlueWallet | `io.bluewallet.bluewallet` | Bitcoin/UTXO |

Thirteen phases, A0–A12 (3.4): baseline, install, create wallet, import
wallet, receive tx, send tx, add token/network, lock/logout, delete wallet,
clear cache, clear storage, uninstall/reinstall, backup/restore. A capture is
taken after each. Full table in `Experiment_Setup/README.md`.

A pilot runs one wallet end to end before committing to all three (3.5).

Test-network transactions and researcher-created wallets only — never real
wallets, real funds, or anyone else's data.

## Environment

The experiment requires a local machine with the Android SDK and hardware
virtualisation. It cannot run in a cloud container: the Android emulator needs
KVM (or macOS Hypervisor), which sandboxed environments don't expose.

`Experiment_Setup/00_check_prereqs.sh` reports what's missing before a run.

Working on the thesis text, the tooling, or the analysis needs none of that —
only `capture` requires a live device. `diff` and `report` work offline on
saved captures.

## Conventions

- Shell scripts: `set -euo pipefail`, check for required tools up front, fail
  with a message that says what to do about it.
- Everything that touches evidence gets hashed and logged — the chain of
  custody is part of the result, not overhead.
- Prefer reporting what was observed over inferring what it means;
  `suggested_status` in the persistence matrix is explicitly labelled as a
  starting point for the researcher to confirm.
- A negative result is a result. "The private key could not be recovered" says
  something real about the app's protection and is worth reporting as a
  finding (3.6).

## Status

- Chapters 1 (Introduction) and 3 (Methodology) — drafted in full.
- Chapter 2 (Literature Review) — structured, a handful of real sources cited;
  needs more, especially Android Keystore and evidential-value frameworks.
- Chapters 4–8 — stubs, blocked on experiment data.
- Experiment phases A0–A12 — not yet run.
- Ethics — submitted; data-collection stage not yet confirmed.
