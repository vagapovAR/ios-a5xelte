# ZEROLTE (Galaxy S6 edge SM-G925F, Exynos 7420): progress

Port target for the `wardevsa/ios-a5xelte` tree. Same method as the A5 2016
(Exynos 7580) -> S7 (Exynos 8890) -> Note FE (Exynos 8890) chain: XNU 8796,
4 KiB pages, Samsung BOOT loader, iOS 16 userland from an iPhone X IPSW.
Hardware facts below are from the device unless marked "source".

## 2026-11-21: device identified, first probe executed

**Device**

- SM-G925F, serial `04157df4db261a0d`, currently running a ported S8 ROM
  (`ro.product.model` reports SM-G950F, `ro.product.device` dreamlte; the real
  board is confirmed by the device tree: `Samsung ZERO-F LTE USA rev06 board
  based on Exynos7420(EVT1)`).
- TWRP installed and working, root (`/sbin/su`), USERDATA 55.5 GiB.
- UFS platform `15570000.ufs`, same partition numbering as the S7:
  BOOT `sda5` (28672 KiB = 29 360 128 B), RECOVERY `sda6` (34 MiB),
  SYSTEM `sda15`, USERDATA `sda18` (58 142 720 KiB), EFS `sda3`.
- Backups pulled off the phone into `backup/` (gitignored): `efs-g925f.img`,
  `recovery-g925f.img`, plus `boot-stock-g925f.img` (current ROM BOOT).

**Current BOOT image** (`tools/zerolte-pack-boot.py info boot-stock-g925f.img`)

- page 2048, sha256 `e2a4715aff8d4b4a97e00068a856a32371173ab810c80fc94d5391ed234551e0`
- kernel 21 535 872 B, `kernel_addr=0x10008000`, `ramdisk_addr=0x11000000`,
  `tags_addr=0x10000100`, text_offset `0x205000`, image_size 0, flags 0
- ramdisk 3 190 863 B; DTBH v2, one entry: chip 7420, platform 0x50a6,
  subtype 0x217584da, hw_rev 10..11, offset 0x800, size 0x2e000
- tail `SEANDROIDENFORCE`

**Probe**

- `shim/zerolte/` (`probe.S`, `probe.c`, `fbtext.c/h`) built with Arm GNU
  Toolchain 14.2.rel1 (aarch64-none-elf, Windows host, Git Bash):
  `out/probe.Image` 10 800 B.
- Packed with `tools/zerolte-pack-boot.py pack ... --partition-size 29360128`
  into `probe-boot.img` (3 397 648 B, sha256
  `8ef9db1ccf54e537dce2656ecb89f1874c83ce09c402535f417cb8d76fdc2f8b`).
- Written with `dd` to `sda5` only, read-back sha256 matched. Nothing else was
  written. The probe is read-only: no storage, EFS, PMIC or MMU changes; it
  requests TWRP through PMU `0x105c0000`.

**Device photo (2026-11-21), all values read off the panel**

| Field | Value | Meaning |
| --- | --- | --- |
| EL | 1 | S-Boot hands off at EL1 |
| SCTLR | 0x30c5183e | MMU, D-cache off (same as S7) |
| FDT | 0x4a000000 | Linux DTB, parsed OK (chosen initrd found) |
| IMAGE | 0x40205000 | our `_start` = **0x40000000 + text_offset 0x205000** |
| MIDR | 0x410fd032 | boot CPU is Cortex-A53 r0p2 (little cluster) |
| MPIDR | 0x80000100 | aff1=1 cluster 0 cpu 0, as on the S7 |
| MMFR0 | 0x1122 | **no 16 KiB granule -> 4 KiB XNU, as on S7/A5** |
| PFR0 | 0x2222 | AArch64 EL0/EL1 |
| ISAR0 | 0x11120 | AES/SHA1/SHA2, **no LSE** (same as S7) |
| CNTFRQ | 0 | read 24 MHz from the ADT (`exynos7420.dtsi`) |
| TRIG | 0x48 | DECON_F `0x13930000+0x6b0` before we write 0x2058 |
| INITRD | 0x43000000 .. 0x4330b04f | 3 190 863 B, matches the header |
| 16K PAGES | NO | confirms the 4 KiB path |
| countdown | "TWRP EN 39 S" | reset-to-recovery path reached |

**Confirmed follow-up:** after the 60 s countdown the phone rebooted by itself
into TWRP 3.3.1-0 (`adb`: `product:zeroltexx model:SM_G925F device:zerolte`,
`ro.board.platform=exynos7420`, UFS `15570000.ufs`). So both halves of the
probe work: the framebuffer console and the Exynos7420 PMU reset to recovery.

**Conclusions**

- S-Boot loads the kernel at `RAM base 0x40000000 + text_offset` (not at
  `kernel_addr`), so keeping the stock `text_offset` in the Image header is
  mandatory. That is why the packer copies it.
- The handoff is otherwise identical in shape to herolte: EL1, MMU off,
  FDT in x0, initrd in the chosen node, CNTFRQ 0, no 16 KiB, no LSE.
- Display path works with the uniLoader values (FB `0xe2a00000`, DECON_F
  `0x13930000`, trigger `+0x6b0` = `0x2058`), even though the pre-write value
  differs from the S7 (`0x48` vs `0x12b0`).
- PMU `0x105c0000` INFORM2/INFORM3/SWRESET is correct for 7420
  (`regs-pmu-exynos7420.h`), same offsets as 8890.

**Hardware map for the next stages (source: LineageOS universal7420 DTS)**

| Item | zerolte | herolte (for comparison) |
| --- | --- | --- |
| GIC | GIC-400 dist `0x11001000`, cpu `0x11002000` | same |
| Timer | 24 MHz, PPI | 26 MHz |
| UFS | `0x15570000` (`ufs-exynos`) | `0x155a0000` |
| DECON_F / DSIM0 | `0x13930000` / `0x13900000` | `0x13960000` / `0x13950000` |
| GPU | Mali-T760 MP8 `0x14ac0000`, IRQ 240/241/242 | Mali-T880 MP12, same base |
| RAM | `0x40000000` + 3 GiB, single bank, top at 4 GiB | `0x80000000` + 3 GiB (2 banks) |
| PMU | `0x105c0000` | same |
| PMIC | S2MPS15 class (check `zero_common.dtsi`) | S2MPS16 |

**Next**

1. TWRP after the probe (the phone reboots into it by itself).
2. `xnu_boot` loader for zerolte: use the probe's memory map, console on
   `0xe2a00000`, text_offset copied from the stock boot.
3. XNU board target `ZEROLTE` on top of the herolte patches: GIC-400
   `0x11001000`, 24 MHz timer, DECON_F `0x13930000`, 4 KiB pages.
4. UFS driver adaptation (`15570000`, S-Boot already brought the link up).
5. Then touch (Synaptics), panel, GPU (T760), audio, Wi-Fi (BCM4358).

## 2026-11-21: loader, ADT and the ZEROLTE board target

- `shim/zerolte/xnu_boot.{S,c}` built (12 256 B). RAM window
  0x80000000..0xc0000000, log page 0x7ffff000, PMU reset to TWRP on failure.
  Image packed into BOOT alone (`loader-only-boot.img`, sha256
  `3cd7a4a98546f40e2956d19df7c478461800ecdc1156f112b80b5c8d82c7f64d`) and
  run on the phone: the panel showed `ZEROLTE XNU LOADER`,
  `LOADER FAIL: BAD SWEETXNU PAYLOAD` and the 30 s countdown, i.e. the
  framebuffer path, the payload parser, the error screen and the reset path
  all execute on Exynos 7420.
- `tools/mkadt_zerolte.py`: 9 896-byte ADT (dram 0x80000000 + 1 GiB, iPhone 8
  canvas, GIC 0x11001000, timebase 24 MHz, 4x A53 + 4x A57). Without
  `research/ipsw-x/d22ap.adt` it omits the iPhone `/product` node; enough for
  the kernel console, needed again before UIKit.
- `xnu/patches/0350-zerolte-board-target.patch` (229 lines, 6 files): adds
  `MACHINE_CONFIG=ZEROLTE` as `ARM64_BOARD_CONFIG_A5XELTE +
  ARM64_BOARD_CONFIG_ZEROLTE`, its own `config/MASTER.arm64.zerolte`, FB
  constants (0xe2a00000, 1440x2560, stride 5760, 8 blocks), marker page
  0x7ffff100, boot MPIDR 0x100, and skips the Exynos 7580 key/touch/eMMC
  probes. Validated with `git apply` on xnu-8796.141.3 + the full series.
- `.github/workflows/xnu.yml`: ZEROLTE added to the firehose flags and the
  push branches.

**Next: build the kernel.** Fork the repository (the user has a GitHub
account), push this tree, run the `xnu` workflow with
`machine_config=ZEROLTE`, download `kernel.development.zerolte`, then pack
`xnu_boot.Image` + `mkpayload.py` output + `zerolte.adt` with
`tools/zerolte-pack-boot.py`. First expected result: XNU console text on the
DECON framebuffer; storage follows after the UFS adaptation.

Decision 2026-11-21: build locally on the user's hackintosh instead of
Actions. `tools/zerolte-macos-build.sh` reproduces the workflow (Xcode 15,
dxb pinned at 663906528d1c, patches copied, firehose rewritten,
`MACOS_VERSION=13.5 KERNEL_CONFIG=DEVELOPMENT MACHINE_CONFIG=ZEROLTE`) and
copies the result to `build-zerolte/out/`. The phone stays in the dev state
(loader in BOOT, 30 s -> TWRP); stock BOOT is one `dd` away.

