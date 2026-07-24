# Integrating deepgent with Claude (MCP)

deepgent can run as an MCP server so an external Claude client (Claude Code,
Claude Desktop, or a claude.ai connector) can call its tools directly.

```
deepgent mcp                 # stdio server, deterministic tools only
deepgent mcp --allow-task    # also expose run_task (costs API, edits files)
```

## Tools exposed

Deterministic, no hardware, no API cost:

- `hw_check(config)` - pin / I2C / power conflict detection for a carrier board
- `boards_catalog(family?)` - the supported board-type catalog
- `matrix_query(claims, stack, component, rules?)` - compatibility with inference
- `matrix_analyze(claims, component, universe?, rules?)` - contradictions + next cell
- `accuracy_score(predictions, truth, kind, iou)` - VOC mAP / top-1
- `skills_eval(ablation)` - skill-lift promote/keep/retire
- `facts(assertions)` - confidence-calibrated fact arbitration
- `reflect(tool, error)` - taxonomy-classified root-cause replan

With `--allow-task` (gated because it costs API and edits files):

- `run_task(task, budget)` - the full agent loop (writes code, reviews, tests)

String arguments accept either inline JSON or a path to a file with that JSON.

## Register with Claude Code

```
claude mcp add deepgent -- deepgent mcp
# or, to allow the agent to run tasks:
claude mcp add deepgent -- deepgent mcp --allow-task
```

## Register with Claude Desktop

Add to `claude_desktop_config.json` (Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "deepgent": {
      "command": "deepgent",
      "args": ["mcp"]
    }
  }
}
```

Use `"args": ["mcp", "--allow-task"]` to expose the task runner. The
`ANTHROPIC_API_KEY` in deepgent's environment is only needed for `run_task`;
the deterministic tools need no key.

## claude.ai web connector

Run an HTTP transport and register it as a custom connector:

```
deepgent mcp --transport streamable-http
```

## Notes

- The stdio transport owns stdout for the MCP JSON-RPC channel; deepgent's logs
  go to stderr, so never mix other output onto stdout when running as a server.
- The deterministic tools preserve deepgent's guarantees: no hardware fact is
  fabricated, and every conflict/claim/score is computed from the input.
