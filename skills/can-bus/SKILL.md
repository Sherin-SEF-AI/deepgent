---
name: can-bus
description: SocketCAN, CAN-FD, sample point, bus-off recovery.
applies_to: TI TCAN4550 controller+transceiver / TCAN1042, NXP TJA1051 transceivers
status: fact-verified
---

# can-bus

> Fact-verified: the facts below were retrieved from public datasheets
> ingested into the knowledge corpus and each cites its source document
> and section. No value is asserted from memory. Board-specific wiring and
> full register maps still require the complete datasheet or on-hardware
> verification. Needs a paired golden and owner review for full Part A3.

Scope: SocketCAN, CAN-FD, sample point, bus-off recovery.

When to reach for it: Bringing up a CAN or CAN-FD node and designing its error/low-power behavior.

## Methodology

- Set the sample point deliberately per the network; the wrong sample point causes intermittent errors that look like wiring faults.
- Terminate with 120 ohm at both physical bus ends only; extra or missing termination degrades signal integrity.
- Design bus-off recovery explicitly: a node that goes bus-off and never recovers is a silent single point of failure.

## Verified facts (with provenance)

- Bus-off recovery follows ISO 11898-1:2015 and cannot be shortened by setting or resetting CCCR.INIT; on bus-off the controller sets CCCR.INIT itself and halts bus activity until the recovery sequence completes (TCAN4550 datasheet, page 86).
- To support CAN-FD at 2 and 5 Mbps the clock/crystal needs 0.5 percent frequency accuracy; a minimum of 20 MHz is required for 2 Mbps and 40 MHz is recommended (TCAN4550 datasheet, s9.1.1).
- Low-power standby is entered by driving the STB pin high; the transmitter and normal receiver are disabled and the bus is biased to ground to minimize supply current, leaving only the low-power receiver monitoring the bus (TCAN1042 datasheet, s9.4.3).
- Transceiver variants differ in bus-fault voltage rating (for example plus/minus 58 V base vs plus/minus 70 V H variants) and in whether they support remote wake (TCAN1042 datasheet, pin/mode selection table).

## Retrieve or verify (still needed)

- your network's nominal and data bitrate and the required sample point.
- your vehicle/device DBC message layout (owner-supplied; no public doc).
