---
name: imu-integration
description: Allan variance, bias, thermal drift.
applies_to: ST LSM6DSR 6-axis IMU
status: fact-verified
---

# imu-integration

> Fact-verified: the facts below were retrieved from public datasheets
> ingested into the knowledge corpus and each cites its source document
> and section. No value is asserted from memory. Board-specific wiring and
> full register maps still require the complete datasheet or on-hardware
> verification. Needs a paired golden and owner review for full Part A3.

Scope: Allan variance, bias, thermal drift.

When to reach for it: Integrating and characterizing a 6-axis IMU for fusion.

## Methodology

- Characterize noise from a long static log with an Allan-variance plot and set the filter's process noise from it, rather than guessing.
- Log temperature and model bias-vs-temperature; the zero-rate/zero-g level drifts and a single room-temperature calibration is insufficient.
- Verify axis sign and frame with a known rotation before feeding the estimator.

## Verified facts (with provenance)

- Accelerometer full-scale ranges are plus/minus 2, 4, 8, and 16 g; gyroscope full-scale ranges are plus/minus 125, 250, 500, 1000, 2000, and 4000 dps (LSM6DSR datasheet, s4.1 Table 2).
- Both accelerometer and gyroscope output data rates are selectable from 12.5 Hz up to 6667 Hz (LSM6DSR datasheet, page 10 characteristics table).
- Zero-g level and zero-rate level describe the deviation of the actual output from the ideal at rest, and are the per-device offsets that must be calibrated and tracked over temperature (LSM6DSR datasheet, s4.6.2).
- The device provides a smart FIFO (up to 9 kbytes) and an auxiliary SPI for OIS gyroscope output (LSM6DSR datasheet, features summary).

## Retrieve or verify (still needed)

- the noise-density and bias-stability values for your unit (datasheet typicals, confirmed by your Allan-variance measurement).
- the register-level ODR/full-scale configuration (CTRL registers) for your rate.
