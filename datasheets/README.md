# Datasheet drop folder (for RAG ingest)

Put public datasheet and reference-manual PDFs here. deepgent ingests them into
the server-side knowledge corpus, and the hardware skills are then completed
with real, provenance-carried facts (never invented from memory).

## Rules (hard)

- PUBLIC documents only: vendor datasheets, reference manuals, kernel docs,
  open specs. No NDA material, no DeepMost-derived content (CLAUDE.md s1, s21).
- PDFs are gitignored: they are vendor-copyrighted and never committed. Only
  this README is tracked. The corpus lives server-side (CLAUDE.md s19).

## How to label (so provenance is exact)

Name each file so the chip/device and version are clear, or add a line to
`manifest.txt` in this folder. Either of these works:

- Filename: `imx219_sensor_datasheet.pdf`, `agx-orin_module_datasheet.pdf`,
  `bmi088_imu_datasheet.pdf`
- Or a `manifest.txt` with `filename | chip | version-range`, one per line:
    imx219_ds.pdf | IMX219 | csi-2
    orin_module.pdf | AGX-Orin | l4t-r36
    bmi088.pdf | BMI088 | -

## What to gather (only for devices you actually use)

Match documents to the hardware skills that are still blocked. Grab the ones
for your real BOM; skip the rest.

- Jetson platform: AGX Orin module datasheet + design guide; JetPack/L4T docs
- Cameras: the image sensor datasheet (e.g. IMX/AR0 series you use); the
  SerDes datasheet for GMSL2/FPD-Link links; MIPI CSI-2 notes
- Other sensors: the interface/datasheet for your lidar, radar (mmWave), IMU,
  and GNSS receiver
- Buses: CAN transceiver datasheet + your DBC; STM32 reference manual; ESP-IDF
  docs for your part

## Then

Tell me the folder is populated. I start the knowledge server, ingest each PDF
with its chip/version tag, verify a retrieval returns provenance, and complete
the matching hardware skills from retrieved facts.
