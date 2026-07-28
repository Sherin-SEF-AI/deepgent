---
name: radar-integration
description: mmWave config, CAN/Ethernet radar.
applies_to: TI IWR6843 60 GHz FMCW mmWave radar
status: fact-verified
---

# radar-integration

> Fact-verified: the facts below were retrieved from public datasheets
> ingested into the knowledge corpus and each cites its source document
> and section. No value is asserted from memory. Board-specific wiring and
> full register maps still require the complete datasheet or on-hardware
> verification. Needs a paired golden and owner review for full Part A3.

Scope: mmWave config, CAN/Ethernet radar.

When to reach for it: Integrating a 60 GHz FMCW mmWave radar and choosing a chirp profile.

## Methodology

- Chirp/profile config trades range, velocity, and resolution; there is no single good config, tune to the use case.
- Ghost and multipath detections are expected; filter them in the consumer rather than assuming they are absent.
- Know whether your firmware emits detections/point-clouds or tracks before writing the consumer.

## Verified facts (with provenance)

- The IWR6843 operates in the 60 to 64 GHz band (IWR6843 datasheet, receiver parameter table).
- Receiver noise figure is about 12 dB (60-64 GHz), maximum gain 48 dB with 2 dB gain steps over an 18 dB range, and IF bandwidth is 10 MHz (IWR6843 datasheet, receiver parameter table).
- ADC sampling rate is 25 Msps in real (2x) mode and 12.5 Msps in complex (1x) mode, at 12-bit resolution (IWR6843 datasheet, receiver parameter table).

## Retrieve or verify (still needed)

- the chirp parameters (slope, ADC samples, frames) valid for your required range and velocity.
- the output interface (CAN/SPI/Ethernet) and format your firmware emits.
