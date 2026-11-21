#!/usr/bin/env bash
# Build kernel.development.zerolte on a local macOS host, the same way
# .github/workflows/xnu.yml does on a runner, but incremental between runs.
#
#   tools/zerolte-macos-build.sh [workdir]      # incremental
#   tools/zerolte-macos-build.sh --clean [dir]  # wipe the build tree first
#
# Needs: Xcode (15.x preferred), Homebrew, ~10 GiB free. sudo is used once to
# stub `xcodes` (build.sh only checks that it exists) and to select Xcode.
# The result is copied to workdir/out/kernel.development.zerolte.
#
# Between runs the patched xnu tree is reset to the pristine tag (otherwise an
# edited patch would be "skipped as already applied" and the build would
# silently use stale code); object files are kept, so only the patched files
# recompile.
set -euo pipefail

CLEAN=0
if [ "${1:-}" = "--clean" ]; then
    CLEAN=1
    shift
fi

REPO=$(cd "$(dirname "$0")/.." && pwd)
WORK=${1:-$REPO/build-zerolte}
# darwin-xnu-build does not quote $WORK everywhere; a space in it splits paths
# ("cp: .../Проект по умолчанию/..." -> "умолчанию/... is not a directory").
case "$WORK" in
*" "*)
    SAFE="$HOME/zerolte-build"
    echo "work dir '$WORK' contains a space; using $SAFE instead"
    WORK="$SAFE"
    ;;
esac
DXB_REPO=https://github.com/blacktop/darwin-xnu-build
DXB_SHA=663906528d1cd5ea8fde7de6f16de73db9511549
MACOS_VERSION=13.5          # xnu-8796, the iOS 16 generation
KERNEL_CONFIG=DEVELOPMENT
MACHINE_CONFIG=ZEROLTE
START=$(date +%s)

[ "$(uname -s)" = Darwin ] || { echo "run this on macOS" >&2; exit 1; }

echo "== dependencies =="
# No Homebrew: Intel macOS 15 is no longer supported by it. The tools are
# installed by hand: jq (system), gum/xcodes/cmake/ninja (stubs in
# /usr/local/bin, only checked by darwin-xnu-build), GNU bash 5.
missing=""
for tool in git python3 curl jq gum xcodes cmake ninja; do
    command -v "$tool" >/dev/null || missing="$missing $tool"
done
if [ -n "$missing" ]; then
    echo "missing:$missing" >&2
    echo "install them in /usr/local/bin (see ZEROLTE_PROGRESS.md, 'local macOS')" >&2
    exit 1
fi

echo "== Xcode =="
XC=$(ls -d /Applications/Xcode_15*.app 2>/dev/null | sort -V | tail -1 || true)
[ -n "$XC" ] || XC=$(ls -d /Applications/Xcode*.app 2>/dev/null | sort -V | head -1 || true)
[ -n "$XC" ] || { echo "no /Applications/Xcode*.app found" >&2; exit 1; }
echo "using $XC"
sudo xcode-select -s "$XC"
if ! command -v xcodes >/dev/null; then
    printf '#!/bin/sh\nexit 0\n' > /tmp/xcodes.stub
    chmod 755 /tmp/xcodes.stub
    sudo mkdir -p /usr/local/bin
    sudo cp /tmp/xcodes.stub /usr/local/bin/xcodes
    rm -f /tmp/xcodes.stub
fi

echo "== darwin-xnu-build @ ${DXB_SHA:0:12} =="
if [ "$CLEAN" = 1 ]; then
    echo "removing $WORK/dxb"
    rm -rf "$WORK/dxb"
fi
mkdir -p "$WORK"
if [ ! -d "$WORK/dxb/.git" ]; then
    git init -q "$WORK/dxb"
    git -C "$WORK/dxb" remote add origin "$DXB_REPO"
fi
git -C "$WORK/dxb" fetch -q --depth 1 "$DXB_REPO" "$DXB_SHA"
git -C "$WORK/dxb" checkout -q FETCH_HEAD

if [ -d "$WORK/dxb/xnu/.git" ]; then
    echo "== resetting the patched xnu tree =="
    git -C "$WORK/dxb/xnu" checkout -q -- .
    git -C "$WORK/dxb/xnu" clean -qfd
else
    echo "== first build: the script will clone xnu =="
fi

cp "$REPO"/xnu/patches/*.patch "$REPO"/xnu/patches/*.sh "$WORK/dxb/patches/"

echo "== firehose: plain arm64, no ARMv8.1 atomics =="
python3 - "$WORK/dxb/build.sh" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
old = 'ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"'
new = ('ARCHS="arm64" VALID_ARCHS="arm64" OTHER_CFLAGS="-mkernel -nostdinc '
       '-Wno-packed -mcpu=cortex-a53 -march=armv8-a+crypto"')
text = path.read_text()
if new in text:
    print('firehose: already patched')
elif old in text:
    path.write_text(text.replace(old, new))
    print('firehose:', new)
else:
    sys.exit('darwin-xnu-build firehose line changed')
PY

echo "== build (incremental after the first run) =="
cd "$WORK/dxb"
MACOS_VERSION="$MACOS_VERSION" KERNEL_CONFIG="$KERNEL_CONFIG" MACHINE_CONFIG="$MACHINE_CONFIG" \
    bash build.sh 2>&1 | tee "$WORK/build.log"

KERNEL="fakeroot/System/Library/Kernels/kernel.$(echo "$KERNEL_CONFIG" | tr A-Z a-z).$(echo "$MACHINE_CONFIG" | tr A-Z a-z)"
[ -f "$KERNEL" ] || { echo "build finished without $KERNEL, see build.log" >&2; exit 1; }
mkdir -p "$WORK/out"
cp "$KERNEL" "$WORK/out/"
echo "== kernel: $WORK/out/$(basename "$KERNEL")  ($(($(date +%s) - START))s) =="
shasum -a 256 "$WORK/out/$(basename "$KERNEL")"
echo
echo "Copy it next to the loader and pack the BOOT image on the machine with adb:"
echo "  python3 tools/mkpayload.py kernel.development.zerolte zerolte.adt payload.bin --cmdline \"\$CMDLINE\""
echo "  python3 tools/zerolte-pack-boot.py pack boot-stock-g925f.img shim/zerolte/out/xnu_boot.Image xnu-boot.img --append payload.bin --partition-size 29360128"
