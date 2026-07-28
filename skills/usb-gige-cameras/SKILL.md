---
name: usb-gige-cameras
description: UVC, GenICam, Aravis. DRAFT methodology pack, unreviewed, no paired golden.
tier: T2
status: draft-unreviewed
---

# usb-gige-cameras (draft, unreviewed)

> Status: DRAFT. Not owner-reviewed and has no paired golden, so it does
> not yet meet the Part A3 skill contract. Methodology only: every
> device-specific value below is deliberately deferred to retrieval or
> on-hardware measurement, never asserted from memory (CLAUDE.md s1, s23).

Scope: UVC, GenICam, Aravis.

## Methodology and traps

- GenICam/GigE Vision cameras self-describe via their XML; read features from the device, do not hardcode.
- USB3 and GigE both have bandwidth ceilings that cap resolution x fps x cameras; budget bandwidth before adding a stream.
- Aravis and vendor SDKs differ in packet-resend and jumbo-frame handling; dropped frames usually trace to MTU or resend config, not the camera.

## Retrieve or verify (do not assume)

- the camera's GenICam feature set and supported modes (from the device XML).
- host NIC/USB bandwidth and jumbo-frame support.

## Before this becomes a real skill

- Pair it with a golden that fails or exceeds loop budget without it.
- Replace each 'retrieve or verify' item with a provenance-carried fact.
- Owner line-by-line review.
