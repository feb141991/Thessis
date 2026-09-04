# Forensic Artefact Analysis of Cryptocurrency Wallet Applications on Android

MSc Digital Forensics thesis — Cranfield University.
*Recovery, Persistence, and Evidential Value*

## What this is

Tests three Android cryptocurrency wallet apps — MetaMask, Trust Wallet, and
BlueWallet — through a fixed 13-step sequence (install, create/import wallet,
transact, logout, delete, clear cache/storage, uninstall/reinstall, backup/restore)
on a rooted emulator. A forensic capture is taken after each step and diffed
against the baseline and the previous step to track exactly what artefacts
appear and what survives. Each recovered artefact is then scored for its
evidential value.

Research questions:

- **RQ1** — What traces do these apps leave during install, wallet creation,
  use, and removal?
- **RQ2** — Which traces survive cache clearing, wallet deletion, storage
  clearing, uninstall/reinstall, and backup/restore?
- **RQ3** — How does the acquisition method (ADB vs. rooted full-filesystem,
  vs. a commercial forensic tool if available) affect what can be recovered?
- **RQ4** — How much do the recovered traces actually prove about who used
  the wallet, when, and what they did?

## Contents

- `Thesis.pdf` — the formal thesis document (LaTeX, Cranfield CUThesisTemplate2026,
  APA7). Chapters 1–3 (Introduction, Literature Review, Methodology) are drafted;
  Chapters 4–8 depend on experiment data not yet collected.
- `Thesis_Draft.docx` — the same content in plain-language working-draft form.
- `Progress_Summaries/` — dated status/risk snapshots against the original plan.
- `Experiment_Setup/` — scripts and notes for standing up the test environment
  (rooted AVD, wallet APK sideloading).

## Status

As of the latest progress summary (18 Aug): Chapters 1 and 3 drafted in full,
Chapter 2 structured but not yet cited, ethics (CURES) submitted but decision
not yet confirmed, wallet apps agreed but not locked, and the A0–A12
experimental phases not yet started.
