---
name: stm32-baremetal
description: HAL vs LL, DMA, clock tree, low-power modes.
applies_to: ST STM32U5 series (RM0456)
status: fact-verified
---

# stm32-baremetal

> Fact-verified: the facts below were retrieved from public datasheets
> ingested into the knowledge corpus and each cites its source document
> and section. No value is asserted from memory. Board-specific wiring and
> full register maps still require the complete datasheet or on-hardware
> verification. Needs a paired golden and owner review for full Part A3.

Scope: HAL vs LL, DMA, clock tree, low-power modes.

When to reach for it: Bare-metal bring-up and low-power design on an STM32U5.

## Methodology

- Get the clock tree right before any peripheral; most bring-up bugs trace back to clock configuration.
- Choose HAL (fast to start, heavier) or LL/register (lean, unforgiving) per resource budget and keep one per driver.
- On cached cores, DMA plus cache needs explicit coherency handling or you read stale data.

## Verified facts (with provenance)

- The STM32U5 low-power mode hierarchy is Run, Sleep, Stop 0/1/2/3, Standby, and Shutdown, with progressively fewer peripherals functional in deeper modes (STM32U5 RM0456, s10.7 and Table 100).
- A wake-up event can be generated from a peripheral interrupt signal to exit a low-power mode (STM32U5 RM0456, Table 100 note).
- The series supports autonomous peripherals / low-power background autonomous mode (LPBAM) so some peripherals operate while the core is stopped (STM32U5 RM0456, s10.7.2).

## Retrieve or verify (still needed)

- the exact clock-tree source/PLL configuration and per-peripheral clock enables for your part and board (from the reference manual clock chapter).
- the DMA channel-to-peripheral mapping for your transfers.
