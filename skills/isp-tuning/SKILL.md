---
name: isp-tuning
description: AE/AWB, tuning files, HDR modes. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# isp-tuning (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: AE/AWB, tuning files, HDR modes.

## Methodology and traps

- AE and AWB tuning is measured against a reference chart under controlled light, not by eye; define the lighting and target first.
- HDR modes change the sensor readout and the tuning file together; a tuning file from SDR will look wrong in HDR.
- Keep tuning files under version control keyed to sensor + lens + light; a tuning file is only valid for the optical stack it was made on.

## Retrieve or verify (do not assume)

- the ISP tuning-file format and toolchain for this platform.
- the sensor+lens characterization data the tuning depends on.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
