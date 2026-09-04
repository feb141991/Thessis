APK SOURCES FOR THE THREE WALLET APPS
======================================

These three scripts assume the APKs already exist under ./apks/ as:
  apks/bluewallet.apk
  apks/metamask.apk
  apks/trustwallet.apk

How to get each one legitimately, and why they aren't the same process.


BlueWallet — easy, first-party
-------------------------------
BlueWallet publishes signed release APKs directly on GitHub:
  https://github.com/BlueWallet/BlueWallet/releases

1. Download the APK for the version you intend to test (record the exact
   version/tag).
2. Verify its sha256 against the checksum GitHub/the release notes publish
   for that asset, where available.
3. Save it as apks/bluewallet.apk.

This is a first-party, signed artefact — no throwaway-device step needed.


MetaMask and Trust Wallet — Play-Store-only, no first-party APK
------------------------------------------------------------------
Neither app publishes a direct-download APK. The only distribution channel
is the Google Play Store, which does not hand out installable APK files.
Getting a verifiable copy onto the rooted forensics AVD (ForensicsAVD)
therefore takes an extra, documented extraction step:

1. Create a SEPARATE, throwaway AVD with Google Play (the "Google Play"
   image, not "Google APIs") — never install Play Store apps directly on
   ForensicsAVD; keep the extraction device and the test device distinct
   so ForensicsAVD's chain of custody stays clean.

2. Sign into a dedicated test Google account on that throwaway AVD (not
   a personal or supervisor account — this should be the same test
   account used elsewhere in the project, and noted in the ethics/chain-
   of-custody log).

3. Install the target app normally from the Play Store on the throwaway
   AVD. Record the installed version number.

4. Locate the installed package's APK path(s) on the throwaway device:
     adb shell pm path <package>
   Modern Play Store installs are often split (an App Bundle): this may
   return a base.apk plus one or more split_*.apk files. Pull all of them:
     adb pull <each returned path> ./staging/

5. If the app came as a split install, either:
     (a) sideload all the split APKs together with `adb install-multiple`
         on ForensicsAVD (preferred — preserves the install exactly), or
     (b) merge them into a single APK with a tool such as APKEditor, only
         if install-multiple is not viable for the test design.

6. Verify authenticity before trusting the pulled file: compute its
   sha256, then cross-check the same version's signing certificate
   fingerprint against a reputable third-party mirror (e.g. APKMirror),
   which independently verifies developer signing certificates. This
   corroborates the file without relying solely on the Play Store
   session used to pull it.

7. Record in the chain-of-custody log: source device, test account used,
   app name/version/package, every pulled filename and its sha256, the
   verification method, and the date/time of extraction.

8. Copy the verified file(s) into apks/ on the host machine, named
   metamask.apk / trustwallet.apk, then run 03_install_wallets.sh to
   sideload onto ForensicsAVD.

9. Destroy or reset the throwaway Play Store AVD once extraction is
   confirmed — it should not be reused as a test device and should not
   persist alongside ForensicsAVD's evidence.


Why this matters for the thesis
--------------------------------
This extraction procedure is a real methodological step, not an
implementation detail — it should be written into Methodology 3.6
(Acquisition Strategy) or 3.11 (Limitations) as a documented, repeatable
procedure, since it affects the provenance of two of the three apps
under test. Treat step 6 (independent signature verification) as the
key defensibility point: it's what lets you say the sideloaded APK is
the same artefact Google Play would have installed, not a claim resting
on trust in a single source.
