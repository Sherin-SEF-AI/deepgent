# Integrating deepgent with Claude (MCP)

deepgent can run as an MCP server so an external Claude client (Claude Code,
Claude Desktop, or a claude.ai connector) can call its tools directly.

## Install deepgent on your PATH (one command)

```
./install.sh
```

This runs `uv tool install --editable ".[gui]"`, putting `deepgent`, `dg`, and
`deepgent-gui` on your PATH. If the shell can't find them afterward, run
`uv tool update-shell` and restart the shell.

## Run the server

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

## claude.ai web connector (HTTP + auth)

claude.ai reaches a remote MCP server over HTTP, so run the streamable-http
transport with a bearer token and expose it at a URL claude.ai can reach.

```
export DEEPGENT_MCP_TOKEN="$(openssl rand -hex 24)"    # shared secret
deepgent mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

- When `DEEPGENT_MCP_TOKEN` is set, every HTTP request must send
  `Authorization: Bearer <token>`; without it the server warns that the
  endpoint is unauthenticated.
- Expose it publicly with a tunnel or reverse proxy (for example
  `cloudflared tunnel --url http://localhost:8000`) and use the resulting
  https URL when adding the custom connector in claude.ai, with the same bearer
  token as the auth header.
- Prefer TLS in front of the server (the tunnel/proxy provides it); the bearer
  token is the access control, the proxy is the transport security.

## Notes

- The stdio transport owns stdout for the MCP JSON-RPC channel; deepgent's logs
  go to stderr, so never mix other output onto stdout when running as a server.
- The deterministic tools preserve deepgent's guarantees: no hardware fact is
  fabricated, and every conflict/claim/score is computed from the input.
