---
name: camera-module-selection
description: Methodology for selecting and integrating camera modules for edge CV - the interface families (CSI/MIPI, USB/UVC, GMSL2, GigE), shutter and sync trade-offs, and how they constrain the host and pipeline. Categorical interface knowledge only; specific sensor parts, resolutions, and bindings must be read from the datasheet.
---

# Camera module selection and integration

Pick the interface before the sensor: the camera interface constrains which
host you can use, how many cameras you can run, and whether hardware sync is
possible. The sensor part number, resolution, frame rate, and driver bindings
are datasheet facts - never assert them from memory; retrieve or measure them.

## Interface families (categorical trade-offs)

- CSI / MIPI: direct to the SoC's camera interface (Jetson CSI, Pi CSI). Lowest
  latency and CPU overhead, but short cable reach and a fixed number of lanes.
  Needs a kernel driver / device-tree overlay specific to the sensor and host.
- GMSL2 (and similar SerDes): serializes CSI over coax for long reach and many
  cameras (surround-view); requires a deserializer on a carrier board and often
  address translation for identical sensors. See camera-bringup-methodology.
- USB / UVC: plug-and-play via the UVC driver on any host, highest
  compatibility and easiest bring-up, but more latency and CPU/bandwidth cost;
  bandwidth is shared across the USB tree.
- GigE Vision / Ethernet: long reach and industrial framing over the network;
  needs the vendor's SDK and adds network-stack latency.

## Selection drivers (decide by requirement, then verify)

- Reach and count: many cameras or long cables push toward GMSL2 or GigE; one
  short-reach camera fits CSI or USB.
- Latency budget: CSI/MIPI for the tightest glass-to-glass; USB/GigE add
  overhead. Confirm the actual number with a latency trace, do not assume.
- Shutter: global shutter avoids motion skew for fast scenes / AV; rolling
  shutter is cheaper. This is a sensor property - read it from the datasheet.
- Sync: hardware frame-sync (triggered/synced capture) matters for multi-camera
  fusion; confirm the sensor and deserializer support it.

## Integrate and verify with deepgent

- Validate the peripheral design (pins, I2C addresses, power) before wiring:
  `deepgent hw-check --config carrier.json`.
- Bring up one camera, confirm enumeration and format, then scale (see
  camera-bringup-methodology).
- Measure end-to-end: `deepgent profile latency` for per-stage glass-to-glass,
  `deepgent soak` for dropped frames / CSI errors under sustained load.

## Boundary

Sensor part numbers, resolutions, FPS, lane counts, driver/overlay names, and
I2C addresses are datasheet facts. Retrieve them with provenance or read them
from the board; an interface family is categorical, a specific binding is not.
