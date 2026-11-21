#!/usr/bin/env python3
"""Build the zerolte (SM-G925F, Exynos 7420) ADT for the ZEROLTE XNU config.

Derived from mkadt_herolte.py. Addresses come from exynos7420.dtsi, the
phone's live /proc/device-tree, /proc/cmdline and /proc/iomem (see
ZEROLTE_PROGRESS.md). Storage node is /zerolte-ufs at 0x15570000; no touch
or GPU nodes yet.

RAM: the S6 has a single 3 GiB bank 0x40000000..0xfe7fffff. XNU gets
0x80000000..0xc0000000 (1 GiB) for the first boot: above the image/initrd/
FDT (0x40205000, 0x43000000, 0x4a000000) and below the bootloader carve-outs
(ess 0x46000000, tima 0x48002000) and the ION video/mfc regions at 0xe2600000.
"""
import argparse
import os
from pathlib import Path

import adt
import mkadt

DRAM_BASE = 0x80000000      # free window in the live iomem map
DRAM_SIZE = 0x40000000      # 1 GiB
SOC_BASE = 0x10000000       # arm-io ranges base; child regs are relative
FB_BASE, FB_WIDTH, FB_HEIGHT = 0xe2a00000, 1440, 2560
TIMEBASE = 24000000         # exynos7420.dtsi timer clock-frequency
A57_MHZ, A53_MHZ = 2100, 1500


def set_prop(node, name, value):
    for i, (key, flags, _) in enumerate(node.props):
        if key == name:
            node.props[i] = (key, flags, value)
            return
    node.props.append((name, 0, value))


def child(node, name):
    for candidate in node.children:
        if candidate.prop('name') == mkadt.cstr(name):
            return candidate
    raise ValueError(f'missing donor ADT node {name}')


def maybe_child(node, name):
    """As child(), but None when the donor has no such node (no d22ap.adt)."""
    for candidate in node.children:
        if candidate.prop('name') == mkadt.cstr(name):
            return candidate
    return None


def add_haptics(root):
    """/product/haptics as the iPhone X's DeviceTree.d22ap has it: Darwin
    plays vibrations as waveforms on the audio plug-in's "Actuator". Without
    it Darwin looks for an IOKit vibrator the iPhone X has not. Idempotent."""
    product = maybe_child(root, 'product')
    if product is None:
        return
    if any(c.prop('name') == mkadt.cstr('haptics') for c in product.children):
        return

    def phandles(n):
        yield int.from_bytes(n.prop('AAPL,phandle') or b'\0\0\0\0', 'little')
        for c in n.children:
            yield from phandles(c)

    handle = max(phandles(root)) + 1
    product.children.append(mkadt.node('haptics', [
        ('AAPL,phandle', mkadt.u32(handle)),
        ('closed-loop', mkadt.u32(1)),
        ('supports-3rd-party-haptics', mkadt.u32(1)),
    ]))


def add_bluetooth_isp(root):
    """Bluetooth and camera nubs, as the Note FE port (0435/0458). Idempotent."""
    arm_io = child(root, 'arm-io')
    names = {c.prop('name') for c in arm_io.children}
    if mkadt.cstr('bluetooth') not in names:
        arm_io.children.append(mkadt.node('bluetooth', [
            ('device_type', mkadt.cstr('bluetooth')),
            ('compatible', mkadt.cstr('bluetooth,n88')),
            ('transport-speed', mkadt.u32(3000000)),
            ('transport-encoding', mkadt.u32(3)),
            ('vendor-id', mkadt.u32(0x05ac)),
            ('product-id', mkadt.u32(0x12a0)),
            ('coex', mkadt.u32(2)),
            ('local-mac-address', bytes((0x02, 0x5a, 0x45, 0x52, 0x4f, 0x02))),
        ]))
    if mkadt.cstr('isp') not in names:
        arm_io.children.append(mkadt.node('isp', [
            ('camera-rear', mkadt.u32(1)),
            ('camera-front', mkadt.u32(1)),
        ]))


def build(canvas=(750, 1334), dram=(DRAM_BASE, DRAM_SIZE), iphone8=True):
    root = mkadt.build(seed=os.urandom(64), qemu=True)
    if iphone8:
        # 375x667 points at @2x, the panel's 16:9 with no bars, and a home
        # button (type 1) so UIKit gives us a status bar for it.
        set_prop(child(root, 'chosen'), 'display-scale', mkadt.u32(2))
        product = maybe_child(root, 'product')
        if product is not None:
            set_prop(product, 'artwork-device-subtype', mkadt.u32(1334))
            set_prop(product, 'artwork-scale-factor', mkadt.u32(2))
        buttons = maybe_child(root, 'buttons')
        if buttons is not None:
            set_prop(buttons, 'home-button-type', mkadt.u32(1))
        canvas = (750, 1334)
    # The userland is the iPhone X IPSW (iPhone10,3 / D22AP), as on herolte.
    # 'samsung,a5xelte' keeps the shared SweetPlatformExpert IONameMatch.
    set_prop(root, 'compatible', mkadt.cstr('D22AP') + mkadt.cstr('iPhone10,3') +
             mkadt.cstr('samsung,a5xelte') + mkadt.cstr('samsung,zerolte') +
             mkadt.cstr('samsung,exynos7420') + mkadt.cstr('AppleARM'))
    chosen = child(root, 'chosen')
    set_prop(chosen, 'dram-base', mkadt.u64(dram[0]))
    set_prop(chosen, 'dram-size', mkadt.u64(dram[1]))
    set_prop(chosen, 'firmware-version', mkadt.cstr('zerolte-entry'))
    set_prop(chosen, 'system-firmware-version', mkadt.cstr('zerolte-entry'))
    # MobileGestalt derives the UDID from these; synthetic locally administered
    # addresses, not the phone's.
    for name, last in (('wifi0', 1), ('bluetooth0', 2), ('ethernet0', 3)):
        set_prop(chosen, f'mac-address-{name}', bytes((0x02, 0x5a, 0x45, 0x52, 0x4f, last)))
    # sRGB: with "P3" WebKit and PosterBoard draw into 10-bit surfaces the
    # OpenGL ES path never shows. Needs the iPhone product node.
    product = maybe_child(root, 'product')
    if product is not None:
        set_prop(product, 'artwork-display-gamut', mkadt.cstr('sRGB'))
    add_haptics(root)
    add_bluetooth_isp(root)
    cpus = child(root, 'cpus')
    cpu0 = child(cpus, 'cpu0')
    # S-Boot starts on the Cortex-A53 cluster: MPIDR 0x100..0x103 (logical
    # 0..3); the Cortex-A57 cluster, MPIDR 0..3, is logical 4..7. One XNU
    # cluster (homogeneous SMP); cpus=4 keeps the A53s only.
    set_prop(cpu0, 'compatible', mkadt.cstr('arm,cortex-a53') + mkadt.cstr('ARM,v8'))
    set_prop(cpu0, 'reg', mkadt.u32(0x100))
    set_prop(cpu0, 'timebase-frequency', mkadt.u32(TIMEBASE))
    for logical in range(1, 8):
        a57 = logical >= 4
        core = logical - 4 if a57 else logical
        cpus.children.append(mkadt.node(f'cpu{logical}', [
            ('device_type', mkadt.cstr('cpu')),
            # SweetCPU matches IONameMatch 'arm,cortex-a53' (KernelConfigTables).
            ('compatible', (mkadt.cstr('arm,cortex-a57') if a57 else b'') +
                           mkadt.cstr('arm,cortex-a53') + mkadt.cstr('ARM,v8')),
            ('reg', mkadt.u32(core if a57 else 0x100 | core)),
            ('cpu-id', mkadt.u32(logical)),
            ('cluster-id', mkadt.u32(0)),
            ('cluster-type', mkadt.u32(0)),
            ('die-cluster-id', mkadt.u32(0)),
            ('cluster-core-id', mkadt.u32(logical)),
            ('l2-cache-id', mkadt.u32(1 if a57 else 0)),
            ('l3-cache-id', mkadt.u32(0)),
            ('state', mkadt.cstr('stopped')),
            ('timebase-frequency', mkadt.u32(TIMEBASE)),
            ('clock-frequency', mkadt.u32((A57_MHZ if a57 else A53_MHZ) * 1000000)),
            ('bus-frequency', mkadt.u32(100000000)),
            ('memory-frequency', mkadt.u32(1552000000)),
            ('peripheral-frequency', mkadt.u32(TIMEBASE)),
            ('fixed-frequency', mkadt.u32(TIMEBASE)),
        ]))
    arm_io = child(root, 'arm-io')
    set_prop(arm_io, 'device_type', mkadt.cstr('zerolte-io'))
    set_prop(arm_io, 'compatible', mkadt.cstr('samsung,exynos7420-io') +
             mkadt.cstr('arm-io'))
    set_prop(arm_io, 'ranges', mkadt.u64(0, SOC_BASE, 0xf0000000))
    arm_io.children = [n for n in arm_io.children if n.prop('name') == mkadt.cstr('wdt')]
    # GIC-400: distributor 0x11001000, CPU interface 0x11002000 (same as S7).
    arm_io.children.append(mkadt.node('gic', [
        ('compatible', mkadt.cstr('arm,cortex-a15-gic')),
        ('interrupt-controller', mkadt.cstr('master')),
        ('virtual-timer-intid', mkadt.u32(27)),
        ('reg', mkadt.u64(0x11001000 - SOC_BASE, 0x1000, 0x11002000 - SOC_BASE, 0x1000)),
    ]))
    arm_io.children.append(mkadt.node('disp0', [
        ('device_type', mkadt.cstr('display-subsystem')),
        # AppleCLCD (SweetFramebuffer.cpp) matches 'samsung,a5xelte-display'.
        ('compatible', mkadt.cstr('samsung,a5xelte-display') +
         mkadt.cstr('samsung,zerolte-display')),
        ('canvas-width', mkadt.u32(canvas[0])),
        ('canvas-height', mkadt.u32(canvas[1])),
    ]))
    # launchd starts com.apple.wifid only if the device tree has a "wlan" node.
    arm_io.children.append(mkadt.node('wlan', [
        ('device_type', mkadt.cstr('wlan')),
        ('compatible', mkadt.cstr('zerolte,bcm4358')),
    ]))
    root.children = [n for n in root.children if n.prop('name') not in
                     (mkadt.cstr('sweet-fbcon'), mkadt.cstr('sweet-ufs'))]
    # Exynos 7420 UFSHCI (exynos7420.dtsi ufs@0x15570000): standard HCI at
    # +0, vendor HCI +0x100, UNIPRO +0x1000, UFS protector +0x2000.
    root.children.append(mkadt.node('zerolte-ufs', [
        ('reg', mkadt.u64(0x15570000, 0x3000)),
    ]))
    # pe_serial.c looks this node up by name for the kprintf console.
    root.children.append(mkadt.node('a5xelte-fbcon', [
        ('reg', mkadt.u64(FB_BASE, FB_WIDTH * FB_HEIGHT * 4)),
        ('width', mkadt.u32(FB_WIDTH)),
        ('height', mkadt.u32(FB_HEIGHT)),
        ('stride', mkadt.u32(FB_WIDTH * 4)),
    ]))
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('output', type=Path)
    parser.add_argument('--canvas', default=None,
                        help='presented display WxH (default 750x1334, iPhone 8)')
    parser.add_argument('--dram-mb', type=int, default=DRAM_SIZE >> 20,
                        help='MiB of the 0x80000000 window to give XNU')
    parser.add_argument('--full-canvas', action='store_true',
                        help='draw the whole 1440x2560 panel (no scaling)')
    args = parser.parse_args()
    canvas = tuple(int(v) for v in args.canvas.lower().split('x')) if args.canvas else (750, 1334)
    dram = (DRAM_BASE, args.dram_mb << 20)
    blob = adt.serialize(build(canvas, dram, not args.full_canvas))
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes, dram {dram[0]:#x}+{dram[1] >> 20} MiB, canvas {canvas[0]}x{canvas[1]}')
