---
name: esp-idf
description: partitions, WiFi/BLE, OTA, sleep.
applies_to: Espressif ESP32 / ESP32-S3
status: fact-verified
---

# esp-idf

> Fact-verified: the facts below were retrieved from public datasheets
> ingested into the knowledge corpus and each cites its source document
> and section. No value is asserted from memory. Board-specific wiring and
> full register maps still require the complete datasheet or on-hardware
> verification. Needs a paired golden and owner review for full Part A3.

Scope: partitions, WiFi/BLE, OTA, sleep.

When to reach for it: Firmware and power design on an ESP32-class part under ESP-IDF.

## Methodology

- Match the partition table and flash size to the exact part; an OTA that fits in dev fails on a smaller production part.
- OTA needs a rollback and a validity check; a bad image without rollback bricks the field unit.
- Plan Wi-Fi/BLE coexistence explicitly; they share the radio.

## Verified facts (with provenance)

- In Deep-sleep the ULP coprocessor and RTC memory remain powered, so a ULP program stored in RTC slow memory can access peripherals, timers, and internal sensors during deep sleep (ESP32 datasheet, s4.3.2).
- When Wi-Fi is enabled the chip alternates between Active and Modem-sleep; in Modem-sleep the CPU frequency scales automatically with load (ESP32 datasheet, s4 functional description).

## Retrieve or verify (still needed)

- your exact ESP part, flash size, and partition scheme.
- the wake-source and RTC-domain configuration for your sleep strategy.
