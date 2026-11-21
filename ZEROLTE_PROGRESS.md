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

**GitHub (2026-11-21):** fork `vagapovAR/ios-a5xelte`, branch `zerolte`.
Run 44918392643 (commit 3a01e6a) failed after 14 min:
- the libpthread/BearSSL/HFS staging scripts only accepted
  SWEET|A5XELTE|HEROLTE, so `sweet_bearssl/` was never staged and every
  crypto object failed;
- `SweetFramebuffer.cpp:684` calls `notefe_zc_active()` outside the HEROLTE
  guard, so ZEROLTE did not compile.
Fixed in 2461a2d (ZEROLTE added to the three `*.sh`, a `false`
`notefe_zc_active()` for ZEROLTE, patch 0350 regenerated and re-validated with
`git apply`). Run 44920173487 is the retry.

Run 44920173487 compiled the whole kernel (every object, including the staged
BearSSL/pthread/HFS) in 9m48s and reached the link, then failed on undefined
symbols: `SweetIOKitDaemonStandIn`, `SweetNetworkStackStart`, `hakios_net_*`,
`hakios_sta_*` (all from `bsd/dev/herolte_wifi.c`) and
`notefe_brightness_set`. `herolte_wifi.c` was the only `herolte_*` driver
without an `ARM64_BOARD_CONFIG_HEROLTE` guard, and its only caller
(`bsd_init.c:1115`) is inside that guard; the backlight setter is declared
outside the guard in `SweetFramebuffer.cpp` and called by `AppleARMBacklight`.
Fixed in 919887f: the wifi driver is wrapped in the HEROLTE guard and
`notefe_brightness_set` gets a ZEROLTE definition. Run 44921252656 is the
third attempt.



The local macOS path stays available: `tools/zerolte-macos-build.sh`
reproduces the workflow (Xcode 15, dxb pinned at 663906528d1c, patches copied,
firehose rewritten, `MACOS_VERSION=13.5 KERNEL_CONFIG=DEVELOPMENT
MACHINE_CONFIG=ZEROLTE`) and copies the result to `build-zerolte/out/`.
The phone stays in the dev state (loader in BOOT, 30 s -> TWRP); stock BOOT is
one `dd` away.

### Local macOS host (hackintosh, 2026-11-21)

- macOS 15.8 on x86_64 (i5-12400F). Homebrew refuses to install: "Homebrew on
  macOS is only supported on Apple Silicon processors".
- Installed by hand: GNU bash 5.2.37 in `/usr/local/bin/bash` (CI uses brew's
  bash 5), `adb` 1.0.41 (platform-tools; copied to `/usr/local/bin/adb`, not
  symlinked, because a root-owned symlink with 0700 cannot be `readlink`ed),
  and `gum`/`xcodes`/`cmake`/`ninja` stubs in `/usr/local/bin` — darwin-xnu-
  build only runs `command -v` on those four, and never invokes them for a
  plain kernel build with `MACOS_VERSION` set.
- `jq` is the system one. `python3 -m venv` works.
- **Xcode.app is mandatory** (`iig` for the IOKit `.iig` files, plus
  `ctfconvert`); Command Line Tools alone are not enough. CLT clang and the
  15.5 SDK are only used by the host tools.
- The script resets the patched `dxb/xnu` tree before re-applying patches, so
  an edited patch is never silently skipped; object files stay, so reruns are
  incremental. `--clean` wipes `dxb` for a full rebuild.


## 2026-11-21: XNU runs on the S6 edge (first kernel boot)

Run 44921252656 built `kernel.development.zerolte` (17 158 352 B, sha256
`a200f9fb...07c5f`; the LSE check passed) in 17m59s. Payload
(16 530 288 B) + `xnu_boot.Image` (12 256 B) packed into the 28 MiB BOOT
(`xnu-boot.img`, 19 929 104 B, sha256 `58a8b29f...6b74`), written to `sda5`,
read back identical, rebooted.

**The panel shows the XNU console**: platform expert, GIC/CPU-interface setup,
`pe_arm_init_debug` (harmless "no cpu-debug-interface" kprintf), scheduler
clutch defaults, MIG/IPC init, serial KDP, HMAC-SHA256 registration,
`clock_initialize`, libpthread-514.100.2, `MACH processor_registration`
(cluster 0, cpu 0), `initCPU`, SMC self-tests — then a panic:

```
panic(cpu 0 caller 0xfffffff0078125b0):
  mbuf <addr> redzone violation with value 0x... (instead of 0x...,
  using cookie 0x...)
```

(`bsd/kern/uipc_mbuf.c:8498`, reached from `m_free`/the pkthdr reset path.)
So the loader, the ADT (GIC 0x11001000, 24 MHz timer, 4x A53 with
`cpus=1`), the 4 KiB XNU start-up and the DECON console all work on
Exynos 7420. The remaining question is the mbuf redzone check; the exact
values are not yet legible on the photo.

Boot command line used:
`debug=0xc keepsyms=1 -enable_kprintf_spam -noprogress cpus=1`
(no `rd=`: there is no zerolte block driver yet).

### The mbuf redzone panic, analysed

`tools/macho-sym.py` resolves the panic caller: `0xfffffff0078125b0` is
`m_free+0x3c0` (symbol `_m_free$XNU_INTERNAL` at 0xfffffff0078121f0). The
numbers from the screen are self-consistent and precise:

```
mbuf 0xfffffff6500aaf00  value 0x500aaf00  instead of 0x54ab49a0  cookie 0x04a1e6a0
```

`0x500aaf00` is the low 32 bits of the mbuf address, and
`0x500aaf00 ^ 0x04a1e6a0 = 0x54ab49a0`: the stored redzone is the one that
would be computed for an mbuf at `0xfffffff654ab49a0`. So the pkthdr of one
zone element carries the redzone of another (a copy or a reuse without
`m_redzone_init`), not random corruption. `m_redzone_init` only runs in
`MBUF_INIT_PKTHDR`, `m_copy_pkthdr` (twice) and `mbuf_reinit`; the check fires
in `m_free`.

Patch `0351-zerolte-mbuf-redzone-bringup.patch` keeps the panic on other
boards but on ZEROLTE prints the mbuf type/flags/len and re-arms the redzone,
so the boot continues and the owner of the packet becomes visible.

## 2026-11-21: XNU reaches BSD init (second boot)

Kernel `8b52f7c5...` (17 158 592 B), BOOT `96bb61b7...` (19 929 104 B),
command line
`debug=0xc keepsyms=1 -enable_kprintf_spam -noprogress cpus=1 wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin`.

The panel shows the whole run: `initialize_screen: no video - forcing serial
mode` (boot_args.Video is empty; the a5fb console still draws), GIC and
debug-interface setup, MIG/IPC, KDP, libpthread-514.100.2,
`cpu_start() cpu: 0`, `initCPU mpidr=0x100 EL1 IRQs=1`, then

```
SK: netagent is enabled by default for this platform
SKBL: skmem_region_init seg_size 16384, md_seg_size 16384, drv_buf_seg_size ...
Skywalk: running self-tests
Skywalk: sk_copy64_8 ... PASSED
... (all copy/zero/memcmp-mask tests PASSED)
bsd_autoconf: calling kminit
```

No mbuf redzone print on this boot, i.e. the boot-1 mismatch did not
reproduce; 0351 stays as a safety net. The screen stops at `kminit`, which is
the expected "no root device" state (IOKitBSDInit then waits for an IOMedia
with `Content=Apple_HFS`), so the next milestone is storage.

### UFS next

`bsd/dev/herolte_ufs.c` turned out to be SoC-neutral: it maps the ADT node's
`reg` and only uses the standard UFSHCI block plus vendor registers
`+0x100/+0x104/+0x140` (no PHY/PMU/CMU writes; it relies on S-Boot's link).
Patch `0352-zerolte-exynos-ufs.patch` compiles it for ZEROLTE with the node
`/zerolte-ufs` (base 0x15570000) and keeps the `ufsprobe=1` / `rd=ufsroot0`
paths in `IOKitBSDInit` while still skipping the Exynos 7580 key/touch pokes.




