---
name: multi-object-tracking
description: ByteTrack/BoT-SORT, ReID, association tuning.
status: methodology-complete
---

# multi-object-tracking

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: ByteTrack/BoT-SORT, ReID, association tuning.

When to reach for it: Turning per-frame detections into stable tracks with consistent IDs.

## Methodology

- Association tuning dominates tracking quality: the motion gate (IoU or Mahalanobis), the appearance threshold, and the two-stage low-score recovery (ByteTrack's idea) matter more than the detector's marginal mAP.
- Add ReID appearance embeddings only when occlusion causes ID swaps; they add latency and can themselves cause swaps under domain shift. Measure IDF1/HOTA with and without.
- Tune track birth/death (min hits to confirm, max age to keep) to the frame rate and object dynamics; defaults tuned for 30 fps mis-handle 10 fps.
- Evaluate with HOTA (which balances detection and association) alongside MOTA; MOTA can look good while IDs churn.

## Common traps

- A better detector with unchanged association can track worse if new low-confidence boxes fragment tracks.
- Camera motion breaks IoU gating; compensate ego-motion (BoT-SORT's camera-motion term) for moving platforms.

## Definition of done

- HOTA and IDF1 reported, not just MOTA.
- Birth/death and gates tuned to the deployment frame rate and object density.
