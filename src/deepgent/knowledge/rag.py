"""datasheet-rag client and the in-process knowledge MCP tools.

The corpus and index live server-side (section 19); this client only
queries. The MCP tools (search, get_chunk) are granted to the researcher
and architect subagents as mcp__knowledge__* and are wired into sessions
only when a knowledge API is configured.
"""

import json
import os
from typing import Any

import httpx
import structlog
from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

from deepgent.config import DeepgentSettings
from deepgent.errors import ConfigError, KnowledgeError

_logger = structlog.get_logger(__name__)

SERVER_NAME = "knowledge"
_TIMEOUT_S = 20.0

# Provenance fields every RAG answer must carry (fact_guard enforces).
PROVENANCE_FIELDS = ("doc", "section", "version_range", "chip", "hash")


class RagClient:
    """Authenticated client for the knowledge API's RAG endpoints."""

    def __init__(
        self,
        api_url: str,
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=api_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT_S,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise KnowledgeError(f"knowledge API unreachable: {exc}") from exc
        if response.status_code == 401:
            raise KnowledgeError(
                "knowledge API rejected the token; check the configured token environment variable"
            )
        if response.status_code >= 400:
            raise KnowledgeError(
                f"knowledge API error {response.status_code}: {response.text[:300]}"
            )
        return response.json()

    async def search(
        self, query: str, chip: str | None = None, l4t: str | None = None
    ) -> list[dict[str, Any]]:
        payload = await self._request(
            "POST", "/rag/search", json={"query": query, "chip": chip, "l4t": l4t}
        )
        chunks: list[dict[str, Any]] = payload.get("chunks", [])
        return chunks

    async def get_chunk(self, chunk_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", f"/rag/chunk/{chunk_id}")
        return result

    async def ingest(
        self, *, doc: str, chip: str, version_range: str, section: str, text: str
    ) -> dict[str, Any]:
        result: dict[str, Any] = await self._request(
            "POST",
            "/rag/ingest",
            json={
                "doc": doc,
                "chip": chip,
                "version_range": version_range,
                "section": section,
                "text": text,
            },
        )
        return result

    async def query_claim(self, stack: dict[str, str]) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("POST", "/matrix/query", json={"stack": stack})
        return result

    async def search_symptom(self, text: str, hw: str | None = None) -> list[dict[str, Any]]:
        payload = await self._request("POST", "/corpus/search", json={"text": text, "hw": hw})
        tuples: list[dict[str, Any]] = payload.get("tuples", [])
        return tuples


def build_rag_client(settings: DeepgentSettings) -> RagClient:
    """Build a client from settings; raises when unconfigured."""
    api_url = settings.knowledge.api_url
    if not api_url:
        raise ConfigError(
            "knowledge.api_url is not configured; set it in "
            ".deepgent/config.toml or DEEPGENT_KNOWLEDGE__API_URL"
        )
    token = os.environ.get(settings.knowledge.token_env, "")
    if not token:
        raise ConfigError(
            f"{settings.knowledge.token_env} is not set; the knowledge API "
            "requires authentication on every request"
        )
    return RagClient(api_url, token)


def _ok(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _err(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


def build_knowledge_tools(client: RagClient) -> list[SdkMcpTool[Any]]:
    """The knowledge MCP tool set backed by one RagClient."""

    @tool(
        "search",
        "Search datasheet chunks for hardware facts. Answers carry "
        "provenance (doc, section, version_range, chip, hash); if nothing "
        "relevant returns, the answer is unknown, never a guess.",
        {"query": str, "chip": str, "l4t": str},
    )
    async def search(args: dict[str, Any]) -> dict[str, Any]:
        try:
            chunks = await client.search(
                str(args["query"]),
                chip=str(args["chip"]) if args.get("chip") else None,
                l4t=str(args["l4t"]) if args.get("l4t") else None,
            )
        except KnowledgeError as exc:
            return _err(str(exc))
        return _ok({"chunks": chunks, "unknown": len(chunks) == 0})

    @tool(
        "get_chunk",
        "Fetch one datasheet chunk by id with full text and provenance.",
        {"chunk_id": str},
    )
    async def get_chunk(args: dict[str, Any]) -> dict[str, Any]:
        try:
            chunk = await client.get_chunk(str(args["chunk_id"]))
        except KnowledgeError as exc:
            return _err(str(exc))
        return _ok(chunk)

    @tool(
        "query_claim",
        "Query the compatibility matrix for a verified claim about a stack "
        "(keys like l4t, cuda, trt, ds, ros, sensor, serdes). Status is "
        "verified_pass, verified_fail, or unknown; claims carry an "
        "evidence_run_id and verified_at, never model opinion.",
        {"stack": dict},
    )
    async def query_claim(args: dict[str, Any]) -> dict[str, Any]:
        stack = args.get("stack")
        if not isinstance(stack, dict) or not stack:
            return _err("stack must be a non-empty mapping of component to version")
        try:
            result = await client.query_claim({str(k): str(v) for k, v in stack.items()})
        except KnowledgeError as exc:
            return _err(str(exc))
        return _ok(result)

    @tool(
        "search_symptom",
        "Search the failure corpus for previously resolved failures matching "
        "a symptom; results carry root_cause, fix, and verification_run_id.",
        {"text": str, "hw": str},
    )
    async def search_symptom(args: dict[str, Any]) -> dict[str, Any]:
        try:
            tuples = await client.search_symptom(
                str(args["text"]),
                hw=str(args["hw"]) if args.get("hw") else None,
            )
        except KnowledgeError as exc:
            return _err(str(exc))
        return _ok({"tuples": tuples, "unknown": len(tuples) == 0})

    return [search, get_chunk, query_claim, search_symptom]


def build_knowledge_server(settings: DeepgentSettings) -> McpSdkServerConfig | None:
    """The knowledge MCP server, or None when no API is configured."""
    try:
        client = build_rag_client(settings)
    except ConfigError:
        _logger.debug("knowledge_server_unconfigured")
        return None
    return create_sdk_mcp_server(
        name=SERVER_NAME, version="1.0.0", tools=build_knowledge_tools(client)
    )
