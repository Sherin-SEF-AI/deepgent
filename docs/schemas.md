# Telemetry, matrix, and corpus schemas

Migrated from CLAUDE.md section 18 after Phase 0.

- task_record: id, ts, class, board, model_mix, tokens, usd, wall_s, loops,
  outcome, failure_tag (taxonomy below), artifacts_path.
- failure taxonomy v0: build_toolchain, build_deps, static_analysis, unit_test,
  deploy_ssh, runtime_crash, perf_miss, accuracy_miss, thermal, flaky_hw,
  knowledge_gap, harness_bug.
- matrix_claim: {stack: {l4t, cuda, trt, ds, ros, sensor, serdes}, claim,
  status, evidence_run_id, verified_at}. Written only by verified runs.
- corpus_tuple: {symptom, hw_config, versions, root_cause, fix_diff_ref,
  verification_run_id, ts}. Candidate tuples auto-drafted by telemetry_tap on
  any failed->passed transition; owner approves before server upload.
