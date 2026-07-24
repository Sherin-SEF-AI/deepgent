---
name: camera-bringup-methodology
description: A safe, provenance-first process for bringing up CSI / GMSL2 cameras on Jetson (identify parts from datasheets, validate the design, verify on hardware) without asserting pin/register/device-tree facts from memory. Process and tool mapping only; every concrete value must be retrieved or measured.
---

# Camera bring-up methodology (CSI / GMSL2 on Jetson)

The hard rule first: pin assignments, I2C addresses, device-tree bindings,
deserializer registers, and voltage rails are hardware-specific facts. Never
state them from memory. Retrieve them from the sensor/deserializer/carrier
datasheets (with provenance) or verify them empirically on the board. "Unknown"
is an acceptable answer; a fabricated address is not.

## 1. Identify the exact stack (before touching anything)

- Sensor part number, deserializer (e.g. GMSL2 SerDes), and carrier board.
  Confirm each from the vendor page / datasheet, not from a product name.
- Host + flashed BSP: `cat /etc/nv_tegra_release` on the board gives the L4T
  version; record it in the run artifacts. Driver/BSP support is L4T-specific.
- Whether the sensor is supported by the JetPack-native driver or needs a
  vendor BSP (often gated behind the vendor's portal). If a BSP is required,
  that is a hard dependency; note it and stop guessing.

## 2. Validate the design on paper (deterministic, no hardware)

Assemble a hardware config (peripherals: pins, I2C bus/address, rail, current;
rails: budget) sourced from datasheets, each carrying provenance, and run
`deepgent hw-check --config carrier.json`. It flags:

- pin/mux collisions between the camera(s) and other peripherals,
- I2C address clashes on a shared bus (common with 4 identical cameras: they
  usually need address translation via the deserializer or a mux),
- power-rail budget overruns across the camera set.

Peripherals lacking datasheet provenance are reported as unverified; treat
them as unknown until confirmed.

## 3. Bring up one camera, then scale

- Load the driver / apply the device-tree overlay from the BSP; do not
  hand-edit DT node names from memory.
- Enumerate: check the video node appears and the sensor is probed. Capture a
  frame with a v4l2 tool and confirm resolution/format match the datasheet.
- For multi-camera (surround / synced), confirm the deserializer's aggregation
  and whether hardware frame-sync is available; independent vs synced changes
  the pipeline and the DT.

## 4. Measure, do not assume

- Sustained capture health: run `deepgent soak` while streaming to catch
  thermal/CSI errors and dropped frames over time.
- End-to-end latency: instrument the pipeline (capture -> ISP -> inference ->
  actuation) and run `deepgent profile latency` for a per-stage glass-to-glass
  breakdown with a p99 budget gate.

## 5. Deliver deterministically

Once the facts are confirmed, prefer generators over prose: `deepgent generate
ros2-node` for a consumer node, container manifests for the toolchain, and a
golden task YAML that verifies "all N streams come up in sync" on the board.
Every claim about a pin, address, or binding cites its datasheet source or a
run id; nothing is invented.
