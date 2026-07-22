---
name: ros2-systems
description: ROS 2 systems engineering on Jetson (Humble native on JetPack 6, Jazzy via containers), covering DDS discovery, QoS traps, zero-copy paths, and executor selection.
---

# ROS 2 systems on Jetson (Humble / Jazzy, JetPack 6.x)

Version-tagged facts verified 2026-07-22 against docs.ros.org sources (via
the ros2_documentation repo at matching distro branches), REP 2000, and
NVIDIA Isaac ROS docs.

## Distro/OS matrix

- Humble: Tier 1 on Ubuntu 22.04 amd64+arm64, EOL May 2027. Jazzy: Tier 1 on
  Ubuntu 24.04 amd64+arm64, EOL May 2029. https://www.ros.org/reps/rep-2000.html
- JetPack 6.x rootfs is Ubuntu 22.04 (kernel 5.15), so Humble is the
  native-apt distro on JetPack 6; Jazzy runs only inside an Ubuntu 24.04
  arm64 container there. Prebuilt arm64 debs exist for both (Tier 1), so the
  core stack never needs a source build on matching Ubuntu.
  https://developer.nvidia.com/embedded/jetson-linux-r3643
- Cross-compilation: the official ros2 cross_compile tool is unsupported
  ("not supported anymore"); the documented path is native arm64 builds or
  docker buildx multi-arch images, matching this repo's qemu-binfmt pattern.
  https://docs.ros.org/en/jazzy/How-To-Guides/Cross-compilation.html

## DDS / RMW

- Default RMW is Fast DDS (`rmw_fastrtps_cpp`) on Humble and Jazzy; switch
  per process with `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`. Mixing RMWs in
  one process fails loudly with exit 102.
  https://docs.ros.org/en/jazzy/How-To-Guides/Working-with-multiple-RMW-implementations.html
- ROS_DOMAIN_ID maps to UDP ports as 7400 + 250*domain_id; safe range 0-101
  (Linux also 215-232); each process takes two ports and >120 processes on a
  host can spill into the next domain's range. All nodes sharing a domain on
  a LAN discover each other, which is how someone else's robot appears in
  `ros2 topic list`.
  https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Domain-ID.html
- Multicast simple discovery scales poorly and is unreliable on WiFi (per
  the official docs). The Fast DDS Discovery Server
  (`fastdds discovery --server-id 0`, clients via
  `ROS_DISCOVERY_SERVER=IP:11811`) replaces it, but v2 filtering blinds
  `ros2 topic list` and the CLI daemon unless configured as SUPER_CLIENT via
  `FASTRTPS_DEFAULT_PROFILES_FILE`.
  https://docs.ros.org/en/jazzy/Tutorials/Advanced/Discovery-Server/Discovery-Server.html
- WiFi with large messages: dropped IP fragments pile up in kernel
  reassembly buffers (30 s timeout). Fixes per the DDS tuning guide:
  best-effort QoS, `net.ipv4.ipfrag_time=3`, larger `ipfrag_high_thresh`;
  Cyclone additionally needs `rmem_max` raised plus a min receive buffer in
  its XML. https://docs.ros.org/en/jazzy/How-To-Guides/DDS-tuning.html
- Humble has only `ROS_LOCALHOST_ONLY`; Iron+ (so Jazzy) deprecates it for
  `ROS_AUTOMATIC_DISCOVERY_RANGE` (SUBNET default, LOCALHOST, OFF) plus
  `ROS_STATIC_PEERS`. Scripts using the old variable behave differently
  across the two distros.
  https://docs.ros.org/en/jazzy/Tutorials/Advanced/Improved-Dynamic-Discovery.html

## Performance on embedded

- Intra-process comms: enable per node (`use_intra_process_comms(true)`);
  zero-copy only when publishing and taking `std::unique_ptr`. With multiple
  same-process subscribers, only one (unspecified which) gets the original
  pointer; the rest get copies.
  https://docs.ros.org/en/jazzy/Tutorials/Demos/Intra-Process-Communication.html
- Loaned messages (inter-process zero-copy): Fast DDS only; POD types only
  (strings/sequences silently fall back to heap); publisher loaning on by
  default (`ROS_DISABLE_LOANED_MESSAGES=1` disables); subscription-side
  loaning off by default because it is documented as not safe.
  https://docs.ros.org/en/jazzy/How-To-Guides/Configure-ZeroCopy-loaned-messages.html
- Executors: SingleThreaded, MultiThreaded (parallelism gated by callback
  groups), StaticSingleThreaded (scans entities once at add time; all
  entities must exist at init). EventsExecutor is in-tree from Iron through
  Jazzy under `rclcpp::experimental::executors` (no API/ABI guarantee) and
  absent from Humble's rclcpp.
  https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Executors.html

## QoS traps

- Profile values (rmw/qos_profiles.h): sensor_data = KEEP_LAST/5/
  BEST_EFFORT/VOLATILE; default = KEEP_LAST/10/RELIABLE/VOLATILE.
  https://github.com/ros2/rmw/blob/jazzy/rmw/include/rmw/qos_profiles.h
- Incompatible QoS passes NO messages and raises no error at creation: a
  reliable (default) subscriber on a best-effort sensor topic silently
  receives nothing. Detect via the offered/requested incompatible QoS
  events, `ros2 topic info --verbose`, or `ros2 doctor`'s QoS compatibility
  report (Humble onward).
  https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html

## Isaac ROS on JetPack 6

- All Isaac ROS 3.x targets Humble: 3.0 = JetPack 6.0; 3.2 = JetPack 6.1;
  3.2 Update 1 adds JetPack 6.2. Isaac ROS 4.x moves to JetPack 7 / Ubuntu
  24.04, so JetPack 6 boards stay on 3.2.x.
  https://nvidia-isaac-ros.github.io/releases/index.html
- NITROS implements REP-2007 type adaptation + REP-2009 negotiation for
  GPU-native transport; zero-copy requires all NITROS nodes composed in the
  same process, and mixed graphs fall back to normal messages transparently.
  Supported workflow is the `run_dev.sh` container; on Jetson NVIDIA
  prescribes moving Docker's data dir to NVMe first.
  https://nvidia-isaac-ros.github.io/concepts/nitros/index.html

## Golden-task workflow on deepgent

1. Prefer Humble native on the board for JetPack 6 targets; use Jazzy only
   via arm64 containers (versions.toml [ros2] governs the choice).
2. When a subscriber sees nothing, check QoS compatibility before touching
   the network; when discovery misbehaves on WiFi, move to the discovery
   server rather than tuning multicast.
3. Measure pipeline latency with clocks pinned (see jetson-bringup) and
   composable NITROS/intra-process paths enabled before quoting numbers.
