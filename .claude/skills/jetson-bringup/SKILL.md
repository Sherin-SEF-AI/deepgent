---
name: jetson-bringup
description: AGX Orin bring-up on JetPack 6.x / L4T r36.x, including flashing traps, nvpmodel/jetson_clocks benchmarking discipline, tegrastats format changes, and unattended provisioning.
---

# Jetson AGX Orin bring-up (JetPack 6.x / L4T r36.x)

Version-tagged facts sourced from NVIDIA documentation and forums, retrieved
2026-07-22. When a fact below conflicts with observed board behavior, trust
the board and record the discrepancy.

## Flashing (r36.4.x)

- Recovery mode: power off, hold Force Recovery, press and release Power,
  release Force Recovery. Confirm on the host with `lsusb` showing
  `0955:7023 NVidia Corp` (t234). Flash over the USB-C port next to the
  40-pin header, not the front ports.
  https://docs.nvidia.com/jetson/archives/r36.4.3/DeveloperGuide/IN/QuickStart.html
- Flash host must be Ubuntu 20.04 or 22.04; 24.04 is unsupported and breaks
  `l4t_create_default_user.sh` (addgroup bug on R36.3). Never flash from a VM:
  the device re-enumerates mid-flash and USB passthrough drops it.
  https://forums.developer.nvidia.com/t/usb-connection-issues-when-flashing-jetson-agx-orin-with-jetpack-6-x-5-x-installation-fails/311261
- eMMC: `sudo ./flash.sh jetson-agx-orin-devkit internal`. NVMe rootfs needs
  the initrd flow (`l4t_initrd_flash.sh --external-device nvme0n1p1 -c
  tools/kernel_flash/flash_l4t_t234_nvme.xml --network usb0 ... external`),
  with `l4t_flash_prerequisites.sh` + `apply_binaries.sh` first when using a
  manually downloaded BSP. (QuickStart above)
- initrd flashing tunnels NFS/SSH over the USB gadget network on IPv6
  `fc00:1:1::/48`; a host firewall dropping IPv6 breaks the flash. External
  media must be attached before entering recovery; low-quality USB-C cables
  are a documented failure cause. `flash_l4t_t234_nvme.xml` assumes >= 64GB
  media (edit `num_sectors` + `-S` for smaller).
  https://docs.nvidia.com/jetson/archives/r36.4.3/DeveloperGuide/SD/FlashingSupport.html
- After NVMe flash, first boot may still need the boot device selected in the
  UEFI menu; flashing does not force boot order. (QuickStart above)

## Power and benchmarking discipline

- AGX Orin 64GB nvpmodel modes on r36.4.3: 0=MAXN, 1=15W, 2=30W (factory
  default), 3=50W. Fresh boards benchmark at 30W unless changed. 32GB
  variant: mode 3 is 40W.
  https://docs.nvidia.com/jetson/archives/r36.4.3/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html
- MAXN is unconstrained but not sustained: hardware throttles above the TDP
  budget and NVIDIA calls prolonged heavy MAXN workloads not recommended.
  Sustained-load numbers taken in MAXN can silently throttle. (same page)
- nvpmodel changes persist across reboots; modes changing the GPU
  `tpc_pg_mask` require a full reboot. JetPack 6.2's "Super Mode" applies to
  Orin Nano/NX only; the AGX Orin table is unchanged.
  https://developer.nvidia.com/blog/nvidia-jetpack-6-2-brings-super-mode-to-nvidia-jetson-orin-nano-and-jetson-orin-nx-modules/
- Benchmarks must pin clocks: r36 drives EMC/interconnect frequency via BPMP
  actmon DFS (boost above 30%, reduce below 20% utilization), so unpinned
  frequencies float with load. Run `sudo nvpmodel -m 0` plus `jetson_clocks`
  before measuring; `jetson_clocks` does not persist across reboots
  (`--store`/`--restore`, state file `l4t_dfs.conf`). Note: r36 docs dropped
  the jetson_clocks section; behavior facts are from r35-era docs, tool still
  ships on r36.
  https://docs.nvidia.com/jetson/archives/r35.4.1/DeveloperGuide/text/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html
- Fan behavior is the `nvfancontrol` daemon ("quiet" vs "cool" profiles);
  thermal results depend on the active profile. (r36 power page above)

## tegrastats (r36)

- JP6 consolidates GPU load to one `GR3D_FREQ X%@[F1,F2]` entry (one load
  percentage, per-GPC frequencies in brackets); JP5-era parsers expecting
  `GR3D2_FREQ` break.
  https://docs.nvidia.com/jetson/archives/r36.4.3/DeveloperGuide/AT/JetsonLinuxDevelopmentTools/TegrastatsUtility.html
- EMC_FREQ% is bandwidth utilization relative to current EMC frequency, not
  occupancy. CPU% is load relative to the current (DVFS-scaled) frequency, so
  100% at a low clock is not core saturation; pin clocks before interpreting.
  VDD rails print instantaneous/average milliwatts since start. Interval flag
  is `--interval <ms>` (default 1000), `--logfile <file>` redirects.
  (same page)

## JetPack 6.x version traps

- Within JP6: JP6.0 = L4T 36.3 / CUDA 12.2 / TRT 8.6; JP6.2 = L4T 36.4.3 /
  CUDA 12.6 / TRT 10.3 / cuDNN 9.3; JP6.2.1 = L4T 36.4.4 / CUDA 12.6.10.
  TensorRT jumps a major version inside JP6, so serialized engines from
  JP6.0 do not load on JP6.2.
  https://docs.nvidia.com/jetson/jetpack/release-notes/index.html
- CUDA upgrades independently of L4T via `cuda-compat-orin-<ver>` with
  `LD_LIBRARY_PATH=/usr/local/cuda-X.Y/compat_orin:...` (Orin-specific
  naming); one compat package at a time; JP6.x supports CUDA 12.3-12.8 this
  way. https://docs.nvidia.com/cuda/cuda-for-tegra-appnote/index.html
- Containers: GPU access during `docker build` requires
  `"default-runtime": "nvidia"` in /etc/docker/daemon.json; Jetson's runtime
  is CSV-mode, CDI specs via `nvidia-ctk cdi generate --mode=csv`.
  https://github.com/dusty-nv/jetson-containers/blob/master/docs/setup.md
- Device tree overlays have two paths on r36: `OVERLAY_DTB_FILE` in the board
  conf lands in the UEFI partition (applies to UEFI and kernel); `OVERLAYS`
  in extlinux.conf applies to the kernel DTB only. Place .dtbo under
  `Linux_for_Tegra/kernel/dtb/` before flashing.
  https://forums.developer.nvidia.com/t/where-is-overlay-applied-dtb-on-rootfs/323806

## Unattended provisioning (board farm)

- Skip oem-config by pre-creating the user with
  `Linux_for_Tegra/tools/l4t_create_default_user.sh` before flashing (adds
  sudoers entry). Known bugs: fails if run twice; R36.3 version breaks on
  Ubuntu 24.04 hosts.
  https://forums.developer.nvidia.com/t/l4t-create-default-user-sh/317522
- Headless first boot runs oem-config as a text interface on the serial/USB
  console when no display is attached. (r36 QuickStart)
- Whether openssh-server is active by default post-setup is unverified; the
  provisioning flow must confirm SSH explicitly rather than assume it.
