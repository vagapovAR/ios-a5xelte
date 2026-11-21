# zerolte (SM-G925F, Exynos 7420): XNU / iOS 16 bring-up

Base: the `herolte` branch (Galaxy S7, Exynos 8890), which already solves the
4 KiB XNU, the Samsung S-Boot handoff, GIC-400, the DECON framebuffer console
and the HFS/UFS root. This document separates **facts from sources** from
**device evidence** (marked "probe").

## Hardware map

| Item | zerolte | herolte (for comparison) | Source |
| --- | --- | --- | --- |
| SoC | Exynos 7420, 4x A57 + 4x A53 | Exynos 8890, 4x Mongoose + 4x A53 | device tree |
| Boot CPU | Cortex-A53 r0p2, MIDR 0x410fd032, MPIDR 0x80000100 | A53, MPIDR 0x80000100 | probe |
| Granules | MMFR0 0x1122: 4K and 64K, **no 16K** | same | probe |
| Atomics | ISAR0 0x11120: AES/SHA, **no LSE** | same | probe |
| Timer | 24 MHz, CNTFRQ reads 0 | 26 MHz, CNTFRQ 0 | DTS + probe |
| GIC | GIC-400 dist 0x11001000, cpu 0x11002000 | same | DTS |
| RAM | 0x40000000..0xfe7fffff (3 GiB, one bank) | 0x80000000 + 2 banks | /proc/iomem |
| Bootloader carve-outs | ess 0x46000000, tima 0x48002000+0x200000, avc 0x48204000 | different | /proc/cmdline |
| ION video/mfc | 0xe2600000..0xf1400000 | from 0xc0000000 | DTS |
| Firmware FB | 0xe2a00000, 1440x2560, ARGB8888, stride 5760 | same address and size | uniLoader + cmdline |
| DECON_F | 0x13930000, HW trigger +0x6b0 = 0x2058 (probe read 0x48) | 0x13960000, +0x70 | uniLoader + probe |
| DSIM0 | 0x13900000 | 0x13950000 | DTS |
| UFS | 0x15570000 (`ufs-exynos`) | 0x155a0000 | /proc/device-tree |
| GPU | Mali-T760 MP8, 0x14ac0000, IRQ 240/241/242 | Mali-T880 MP12, same base | DTS |
| PMU | 0x105c0000, INFORM2 +0x808, INFORM3 +0x80c, SWRESET +0x400 | same | regs-pmu-exynos7420.h + probe |
| Audio codec | WM5110 over SPI | different | DTS |
| Wi-Fi | BCM4358 | BCM4359 | source |
| Touch | Synaptics `sec_ts` | Samsung `sec_ts` | DTS |

## What the probe proved (2026-11-21)

`shim/zerolte/` (probe.S/probe.c/fbtext.c) packed into the phone's own BOOT
by `tools/zerolte-pack-boot.py`. One photo, then the phone reset itself into
TWRP 3.3.1-0. Recorded on the panel:

```
EL 1  SCTLR 0x30c5183e  FDT 0x4a000000  IMAGE 0x40205000
MIDR 0x410fd032  MPIDR 0x80000100  MMFR0 0x1122  PFR0 0x2222
ISAR0 0x11120  CNTFRQ 0  TRIG 0x48
INITRD 0x43000000..0x4330b04f   16K PAGES: NO
```

Consequences:

1. **S-Boot loads the kernel at `0x40000000 + text_offset`**, not at the
   header's `kernel_addr`. The stock `text_offset` (0x205000) must be kept in
   the Image header, so the packer copies it. `_start` therefore runs at
   0x40205000.
2. The handoff is shaped like herolte: EL1, MMU off, FDT in x0, initrd in the
   FDT's chosen node, no 16 KiB granule, no LSE.
3. The framebuffer console works with uniLoader's DECON_F values, and the
   PMU reset to recovery is correct for 7420.

## Boot image

- page 2048, `kernel_addr=0x10008000`, `ramdisk_addr=0x11000000`,
  `tags_addr=0x10000100`, `text_offset=0x205000`
- DTBH v2, one entry: chip 7420, platform 0x50a6, subtype 0x217584da,
  hw_rev 10..11, offset 0x800, size 0x2e000
- BOOT (`sda5`) is 28 MiB; the current ROM kernel is 21.5 MiB, so the XNU
  payload goes appended to the loader Image (the `--append` layout), not as a
  ramdisk.

## Memory plan for XNU

```
0x40000000  S-Boot: kernel image 0x40205000, initrd 0x43000000, FDT 0x4a000000
0x46000000  ess_setup (bootloader)
0x48002000  sec_tima_log 2 MiB, 0x48204000 sec_avc_log 256 KiB
0x80000000  XNU RAM window, 1 GiB, top at 0xc0000000   (ZEROLTE config)
0xe2600000  ION mfc_nfw/mfc_fw/video/video_ext
0xfe800000  end of System RAM
```

The window can grow to 0x80000000..0xe2600000 (1.5 GiB) once storage and the
display are up; the loader and the ADT must agree (`--dram-mb`).

## Stages

1. **Probe** — done (2026-11-21).
2. **Loader** — `shim/zerolte/xnu_boot.{S,c}`, builds to 12 256 B: copies the
   payload segments to 0x80000000, builds `boot_args`, hands off with the MMU
   off. Needs the XNU kernel to test.
3. **XNU board target** — `xnu/patches/0350-zerolte-board-target.patch`:
   `MACHINE_CONFIG=ZEROLTE` reuses the A5XELTE code with `ARM64_BOARD_CONFIG_ZEROLTE`
   and its own constants (FB 0xe2a00000, 1440x2560, stride 5760, 8 bootstrap
   blocks of 2 MiB, marker page 0x7ffff100). GIC and timer come from the ADT.
4. **Kernel console** — pack loader + `kernel.development.zerolte` + ADT,
   boot, read the DECON console.
5. **Storage** — adapt `xnu/patches/0204-herolte-exynos-ufs.patch` to
   0x15570000, then put an HFSX root in USERDATA.
6. **Touch, panel scaling, GPU (T760), audio (WM5110), Wi-Fi (BCM4358)**.

## Building

Kernel (needs macOS or GitHub Actions, macOS 13.5 SDK, xnu-8796.141.3):

```sh
gh workflow run xnu.yml -R YOU/ios-a5xelte -f machine_config=ZEROLTE
gh run download RUN_ID -n xnu-kernel-macos-15-intel -D xnu/out
```

Loader (any bare-metal aarch64 GCC, verified with Arm GNU 14.2.rel1):

```sh
cd shim/zerolte && CROSS=aarch64-none-elf- PYTHON=python sh build.sh
```

ADT (needs `research/ipsw-x/d22ap.adt`, extracted from the iPhone X IPSW
with `tools/remotezip.py` + `ipsw img4`):

```sh
python3 tools/mkadt_zerolte.py zerolte.adt --dram-mb 1024
```

Payload and BOOT:

```sh
python3 tools/mkpayload.py kernel.development.zerolte zerolte.adt payload.bin --cmdline "$CMDLINE"
python3 tools/zerolte-pack-boot.py pack boot-stock-g925f.img \
  shim/zerolte/out/xnu_boot.Image xnu-boot.img \
  --append payload.bin --partition-size 29360128
```

### Local macOS build

```sh
tools/zerolte-macos-build.sh            # Xcode 15, 30-60 min
# -> build-zerolte/out/kernel.development.zerolte
```

It mirrors the workflow: pin of blacktop/darwin-xnu-build at
`663906528d1c`, our patches copied into its `patches/`, the firehose line
rewritten for a plain ARMv8.0 arm64 build, then
`MACOS_VERSION=13.5 KERNEL_CONFIG=DEVELOPMENT MACHINE_CONFIG=ZEROLTE`.

### First console boot

```sh
CMDLINE='debug=0xc keepsyms=1 -enable_kprintf_spam -noprogress cpus=1'
```

No `rd=` yet: there is no zerolte block driver, so the first milestone is the
XNU console on the DECON buffer (plus the panics' text). Once the kernel
reaches `arm_vm_init`/`bsd_init`, add the UFS work from stage 5.

## Rules

- Write only BOOT (`sda5`). Keep `boot-stock-g925f.img`, `backup/efs-g925f.img`
  and `backup/recovery-g925f.img` off the phone and out of git.
- To get Android back: `dd if=boot-stock-g925f.img of=/dev/block/sda5` in TWRP.
