---
name: firmware-debugging
description: JTAG/SWD, hard fault analysis, tracing.
status: methodology-complete
---

# firmware-debugging

> Methodology skill: durable engineering practice, not device facts. It
> asserts no hardware-specific value; where a number depends on your
> stack or device, it says to measure or retrieve it. Still needs a
> paired golden and owner review to meet the full Part A3 contract.

Scope: JTAG/SWD, hard fault analysis, tracing.

When to reach for it: Diagnosing crashes and faults in bare-metal or RTOS firmware.

## Methodology

- A hard fault leaves a recoverable trail: capture the stacked registers and the fault-status registers before resetting; they usually point straight at the faulting access.
- Use JTAG/SWD to halt and inspect state (and set data watchpoints); a printf-only workflow misses timing-dependent and fault-state bugs.
- Reproduce with a minimal case; an intermittent fault under the full app is often a stack overflow, DMA-buffer, or interrupt-priority bug that a minimal reproducer isolates.
- Add instruction/data trace (where the core supports it) for bugs that vanish under a debugger's timing.

## Common traps

- Resetting on fault before reading the fault registers, discarding the evidence.
- Heisenbugs that disappear when single-stepping because they are timing/race bugs; use trace, not stepping.

## Definition of done

- Fault root-caused from captured registers/trace on a minimal reproducer, not guessed.
