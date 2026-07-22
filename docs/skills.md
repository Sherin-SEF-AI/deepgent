# Skill packs

Migrated from CLAUDE.md section 11 after Phase 0.

- Format: Agent Skills convention. Directory per skill with `SKILL.md`
  (frontmatter: name, description; body: instructions), optional `references/`,
  `scripts/`. Keep SKILL.md under ~150 lines; deep detail goes in references
  loaded on demand.
- Launch set (Phase 1 builds first three):
  jetson-bringup, tensorrt-quantization, ros2-systems,
  deepstream-pipelines, camera-bringup-gmsl2, can-bus, sensor-fusion,
  training-pipelines, embedded-c-safety, hailo-toolchain.
- Content rules: only non-obvious, durable, version-tagged knowledge. Nothing
  the base model already knows (test by running goldens with the skill absent).
  Every claim carries source + version applicability. No licensed standards text
  (MISRA/ISO rules are enforced by tooling, described only in own words).
- Merge gate: a skill change merges only if the golden suite improves or holds
  with equal-or-lower loop count. `deepgent evals run --diff` produces the
  evidence. Skills are code; they go through PRs and CI.
