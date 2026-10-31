# Installing nx2android

nx2android ports your own Nintendo Switch games to Android. This folder is the whole app: there is nothing to install with pip, and you need no programming. You need:

- a Windows x64 PC, a Mac with Apple Silicon (macOS 14 or later) or a Linux x64 or arm64 PC, with about 30 GB free whichever it is (the tools take 4 GB, a port about twice the game's size);
- an Android device whose GPU is an **Adreno** (Snapdragon) or **Xclipse** (Exynos 2200 and later). Mali and PowerVR GPUs cannot run these games;
- the game's files dumped from your own Switch (the base game NSP or XCI, its update and DLC, in one folder) and your **`prod.keys`** from the same Switch. The tool reads NSP and XCI files; an NSZ must be decompressed to an NSP first.

## 1. Start the app

**Windows x64.** Unzip `nx2android-<version>-windows-x64.zip` anywhere you can write (a short path such as `C:\nx2android` is best) and start **nx2android.exe**. Windows may warn about an unknown app: choose *More info* → *Run anyway*.

A few antivirus engines may flag `nx2android.exe` (on VirusTotal, 3 of 69 flagged v0.1.1, with generic labels such as "Trojan.Stealer" or "BehavesLike.Injector"; Microsoft Defender, Kaspersky, ESET, BitDefender and the other large engines did not). It is a false positive: the app is a Python program packed with PyInstaller, whose small launcher unpacks a compressed archive of the program and runs it, which heuristic scanners mistake for a packed trojan. The app is not code-signed yet, which adds to the score. Its source is on the project's GitHub page, and you can build the same bundle yourself with `python packaging/build_bundle.py`.

**macOS 14 or later on Apple Silicon.** Open `nx2android-<version>-macos-arm64.dmg`, drag **nx2android** onto **Applications**, and start it from Applications (not from the disk image). The app is signed and notarized by Apple, so it opens without a warning. The first time you pick a game folder in Documents, Downloads, the Desktop or on an external drive, macOS asks whether nx2android may read it: allow it.

**Linux x64 with glibc 2.35 or later** (for example Ubuntu 22.04, Debian 12 or Fedora 36, or later) **and Linux arm64 with glibc 2.39 or later** (for example Ubuntu 24.04, Debian 13 or Fedora 40, or later). Unpack the archive and start the app:

```
tar xzf nx2android-<version>-linux-<arch>.tar.gz
nx2android/nx2android
```

It runs under X11 and Wayland. It uses the system's OpenGL/EGL, xkbcommon, fontconfig, D-Bus and Wayland client libraries; most desktops have them, and on Debian or Ubuntu they are `sudo apt install libgl1 libegl1 libxkbcommon-x11-0 libfontconfig1 libwayland-client0 libwayland-egl1 libdbus-1-3`. On Linux arm64 there is no Android NDK or platform-tools from Google; see [Linux: adb and the arm64 NDK](#linux-adb-and-the-arm64-ndk) below.

### Linux: adb and the arm64 NDK

**adb** on Linux arm64 (and, if you like, on Linux x64) comes from your distribution: `sudo apt install adb` (Debian, Ubuntu), `sudo dnf install android-tools` (Fedora), `sudo pacman -S android-tools` (Arch). The setup window shows the command for yours. If the device then shows `no permissions`, install your distribution's Android udev rules (`sudo apt install android-sdk-platform-tools-common`, `sudo dnf install android-tools`, `sudo pacman -S android-udev`) and plug the device in again. An older distribution adb (29.x, as on Ubuntu 22.04 and Debian 12) works: the tool then pushes without compression.

**The Android NDK on Linux arm64.** **Download all missing** fetches a community build of NDK r27c for arm64 Linux (HomuHomu833/android-ndk-custom, about 128 MB), checked against the size and hash the tool pins. The tool labels it "not the build the titles were tested with": the games were tested with Google's own NDK, and the label stays until the community build's ports have been checked on a device.

If the community build does not run on your machine, you can assemble an NDK folder yourself; the tool does not do it for you:

1. Install your distribution's clang, lld and llvm of the same major version as NDK r27c's clang, 18, and its glslc (Debian, Ubuntu: `sudo apt install clang-18 lld-18 llvm-18 glslc`).
2. Download Google's `android-ndk-r27c-linux.zip` (the linux-x86_64 NDK), unpack it, and in its `toolchains/llvm/prebuilt/` copy the `linux-x86_64` folder to a new `linux-arm64` folder beside it. Its `sysroot` and `lib/clang/18` (the clang runtime) are what you keep.
3. In `linux-arm64/bin/`, replace `clang` with a small script that runs your distribution's clang with this folder's runtime and sysroot (a plain link would use the distribution's own runtime, which has no Android libraries), and link `llvm-strip` to the distribution's:
   ```
   #!/bin/sh
   d=$(dirname "$(readlink -f "$0")")/..
   exec clang-18 -resource-dir "$d/lib/clang/18" --sysroot "$d/sysroot" "$@"
   ```
   `chmod +x clang`, then `ln -sf "$(command -v llvm-strip-18)" llvm-strip`.
4. In the setup window, press **Use my own…** on the Android NDK row and choose the NDK folder. The tool checks it and compiles and links a small Android program with it, as it does with any NDK; the row turns green only if that works.

## 2. First-run setup (once)

The first time the app starts, a setup window walks you through four steps. **Back** and **Next** move between them.

1. **The notice.** Read it and press **Accept and continue**: use the tool only with games and keys from a Switch you own; nothing is uploaded; the tools come from Google and Microsoft under their licenses, which the notice links to.
2. **prod.keys.** The window lists any `prod.keys` it finds in the usual emulator folders; pick yours, or choose the file with **Browse…**. It shows which key generation the file reaches, so you can see whether it is new enough for your game.
3. **Tools.** The Android NDK, the .NET SDK and adb, each with a ✓ when it is found. **Download all missing** fetches what is missing (about 1 GB, into your nx2android folder) with progress and the time left. **Cancel download** stops it, and pressing **Download all missing** again resumes where it stopped. If you already have a tool installed, press **Use my own…** on its row and choose it.
4. **Device.** Turn on USB debugging (Settings › About, tap *Build number* seven times, then Settings › System › Developer options › USB debugging), plug the device in, and tap **Allow** on the "Allow USB debugging?" prompt. If the device shows `unauthorized`, `offline` or `no permissions`, the window says how to fix it (unlock the device and tap Allow; replug it; on Linux, install the udev rules, see [Linux: adb and the arm64 NDK](#linux-adb-and-the-arm64-ndk)).

The last page lists the games you can port. On Linux it also offers **Add to app menu**, which puts nx2android in your desktop's application menu so you can start it from there.

**Skip setup** (or closing the window) leaves setup for later: a banner at the top of the main window says what is still missing, and **Continue setup** opens the window again at the first step that is not done. The **Setup** tab shows the same checks at any time.

## 3. Port tab

1. Choose the game's folder. The card under it says which game it found and whether it can be ported: the **Games** tab lists the supported ones.
2. Click **Port**. The first port of a game takes a while: extraction, rewriting the game's code, translating its shaders (2 to 6 minutes on a fast 20-thread PC with an SSD, much longer on a slow one or a hard disk). Later ports reuse what has not changed.
3. The APK and the game's data folder (`<Game>-data`) appear in the game's folder. **Open output folder** shows them.

## 4. Put it on the device

With **USB debugging** on (Settings → About → tap *Build number* seven times, then Settings → Developer options → USB debugging) and the device plugged in, tick **Install on the device when done** before porting, or click **Install on device** afterwards. Allow the PC when the device asks.

## Your signing key

The first port makes a signing key, `signing-key.json`, in your nx2android folder (the folder that also holds `logs`, listed below). Every port is signed with it, which is what lets a new port of a game install over the last one. Keep a backup copy of it somewhere safe.

If the tool says the signing key cannot be read, put your backup copy back. If you have none, you can remove the file on purpose: the next port makes a new key, and each game you ported before must then be reinstalled with `--replace-signer`, which deletes that game's saves on the device.

## When something goes wrong

The status line under the **Port** button shows the cause, and the log at the bottom of the Port tab has the details; lines in red are errors. **Open log** opens the full log of the run, which you can attach to an issue as it is (it holds no keys). The app keeps the logs of the last runs in the `logs` folder of your nx2android folder:

- Windows: `%APPDATA%\nx2android\logs`
- macOS: `~/Library/Application Support/nx2android/logs`
- Linux: `~/.config/nx2android/logs` (or `$XDG_CONFIG_HOME/nx2android/logs`)

Ask on the project's GitHub page (Issues), with the game's title ID, your device and the log. Never post your keys or game files.

The command line is the same program: `nx2android.exe -m porter -h` on Windows, `/Applications/nx2android.app/Contents/MacOS/nx2android -m porter -h` on macOS, `nx2android/nx2android -m porter -h` on Linux.
