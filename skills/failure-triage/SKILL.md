---
name: failure-triage
description: Corpus-first debugging methodology for embedded/CV builds - classify the failure, consult the verified failure corpus before any guesswork, apply a targeted root-cause replan instead of a blind retry, and feed the resolution back to the flywheel. Process and tool mapping; no fabricated root causes.
---

# Failure triage (corpus-first)

When a build, deploy, or on-target run fails, resist the blind retry. A retry
without a root cause wastes budget and re-hits the same wall. Classify, consult
what is already known, then act on the specific cause.

## 1. Classify the failure

Every failure maps to a taxonomy tag: build_toolchain, build_deps,
static_analysis, unit_test, deploy_ssh, runtime_crash, perf_miss,
accuracy_miss, thermal, flaky_hw, knowledge_gap, harness_bug. The tag decides
the next action - a perf_miss is profiled, a deploy_ssh is a reachability/auth
check, a thermal is a power/cooling problem. Unclassifiable is itself a signal
(inspect the raw error, isolate the smallest failing step).

## 2. Consult the corpus before reasoning

The failure corpus holds prior resolved failures with verified fixes. Consult
it first: `deepgent triage --symptom "<error>" --hw <board>` (corpus-first; only
a miss escalates to LLM debugging) and `deepgent reflect --tool <t> --error
"<e>"`, which classifies and attaches the nearest corpus-verified fix as a
targeted replan. A corpus-grounded step is a known-good fix, not a guess.

## 3. Severity decides sequencing

High-severity classes (runtime_crash, accuracy_miss, thermal, flaky_hw,
harness_bug): capture the failing state first - dmesg tail, the tegrastats
window, the run artifacts - before changing anything, so the fix is verified
against evidence rather than a vanished state. In the live task loop the
reflexion_tap hook injects this replan automatically on a tool failure.

## 4. Fix the cause, not the symptom

- unit_test: reproduce the failing assertion and fix the root cause, never edit
  the test to pass.
- static_analysis / CUDA: fix the reported violation at the source; never
  suppress it (see cuda-kernel-safety).
- build_deps: resolve against `versions.toml`; do not pin a random version.
- flaky_hw: re-run under `deepgent soak` to confirm it is real before chasing a
  ghost; check power/thermal stability.

## 5. Feed the flywheel

A failed-to-passed transition drafts a corpus-tuple candidate (symptom, the
classified tag, and the verified fix) for owner approval. Verified fleet runs
become matrix claims. The next occurrence of this failure is then a corpus hit,
not a rediscovery. Never invent a root cause to close a ticket - an unresolved
failure with an honest "unknown" beats a fabricated fix that pollutes the
corpus.
