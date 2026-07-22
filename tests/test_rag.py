"""Knowledge server, RAG client, chunking, and fact_guard."""

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest
from claude_agent_sdk.types import HookContext
from deepgent_server import create_app
from deepgent_server.ingest import chunk_text
from deepgent_server.store import ChunkStore
from fastapi.testclient import TestClient

from deepgent.hooks.fact_guard import fact_guard, filter_chunks_payload, has_provenance
from deepgent.knowledge import RagClient, build_knowledge_tools

TOKEN = "test-token-1234"
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app(tmp_path: Path) -> Any:
    return create_app(db_path=tmp_path / "rag.db", token=TOKEN)


@pytest.fixture
def api(app: Any) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})


class TestServer:
    @pytest.mark.unit
    def test_no_anonymous_reads(self, app: Any) -> None:
        anonymous = TestClient(app)
        for path in ("/healthz", "/rag/chunk/ch-x"):
            assert anonymous.get(path).status_code == 401
        assert anonymous.post("/rag/search", json={"query": "x"}).status_code == 401

    @pytest.mark.unit
    def test_wrong_token_rejected(self, app: Any) -> None:
        bad = TestClient(app, headers={"Authorization": "Bearer wrong"})
        assert bad.get("/healthz").status_code == 401

    @pytest.mark.unit
    def test_missing_token_env_refuses_to_boot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DEEPGENT_SERVER_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="never runs without authentication"):
            create_app(db_path=tmp_path / "x.db")

    @pytest.mark.unit
    def test_ingest_search_round_trip_with_provenance(self, api: TestClient) -> None:
        ingest = api.post(
            "/rag/ingest",
            json={
                "doc": "orin-pinmux.txt",
                "chip": "agx-orin",
                "version_range": "36.x",
                "section": "GPIO07 pin",
                "text": "GPIO07 maps to SOC gpio PP.04 on the 40-pin header.",
            },
        )
        assert ingest.status_code == 200
        chunk_id = ingest.json()["id"]

        search = api.post("/rag/search", json={"query": "GPIO07 header", "chip": "agx-orin"})
        chunks = search.json()["chunks"]
        assert len(chunks) == 1
        for field in ("doc", "section", "chip", "version_range", "hash"):
            assert chunks[0][field]

        fetched = api.get(f"/rag/chunk/{chunk_id}")
        assert fetched.status_code == 200
        assert fetched.json()["section"] == "GPIO07 pin"

    @pytest.mark.unit
    def test_chip_filter_and_missing_chunk(self, api: TestClient) -> None:
        api.post(
            "/rag/ingest",
            json={
                "doc": "d",
                "chip": "orin-nx",
                "version_range": "36.x",
                "text": "CAN0 pins are on the M.2 key E slot header.",
            },
        )
        other = api.post("/rag/search", json={"query": "CAN0 pins", "chip": "agx-orin"})
        assert other.json()["chunks"] == []
        assert api.get("/rag/chunk/ch-nope").status_code == 404


class TestStoreAndChunking:
    @pytest.mark.unit
    def test_search_empty_query_tokens(self, tmp_path: Path) -> None:
        store = ChunkStore(tmp_path / "s.db")
        assert store.search("!!! ???") == []

    @pytest.mark.unit
    def test_chunk_text_splits_on_headings(self) -> None:
        content = "# Power rails\nVDD info.\n\n# Pinmux\nGPIO table."
        chunks = chunk_text(content)
        assert [c.section for c in chunks] == ["Power rails", "Pinmux"]

    @pytest.mark.unit
    def test_oversized_sections_split(self) -> None:
        content = "# Big\n" + ("paragraph text\n\n" * 400)
        chunks = chunk_text(content)
        assert len(chunks) > 1
        assert all(len(c.text) <= 2400 for c in chunks)


class TestRagClient:
    @pytest.mark.unit
    def test_client_against_real_app(self, app: Any) -> None:
        transport = httpx.ASGITransport(app=app)
        client = RagClient("http://testserver", TOKEN, transport=transport)

        async def scenario() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            try:
                await client.ingest(
                    doc="ds.txt",
                    chip="agx-orin",
                    version_range="36.x",
                    section="UART",
                    text="UART1 default baud console on the debug header.",
                )
                chunks = await client.search("UART1 console")
                one = await client.get_chunk(chunks[0]["id"])
                return chunks, one
            finally:
                await client.aclose()

        chunks, one = asyncio.run(scenario())
        assert chunks[0]["doc"] == "ds.txt"
        assert one["section"] == "UART"

    @pytest.mark.unit
    def test_bad_token_is_actionable(self, app: Any) -> None:
        from deepgent.errors import KnowledgeError

        client = RagClient("http://testserver", "wrong", transport=httpx.ASGITransport(app=app))

        async def scenario() -> None:
            try:
                await client.search("anything")
            finally:
                await client.aclose()

        with pytest.raises(KnowledgeError, match="rejected the token"):
            asyncio.run(scenario())

    @pytest.mark.unit
    def test_knowledge_mcp_tools_report_unknown(self, app: Any) -> None:
        client = RagClient("http://testserver", TOKEN, transport=httpx.ASGITransport(app=app))
        tools = {t.name: t for t in build_knowledge_tools(client)}
        result = asyncio.run(tools["search"].handler({"query": "nonexistent xyzzy"}))
        payload = json.loads(result["content"][0]["text"])
        assert payload["unknown"] is True
        asyncio.run(client.aclose())


def _knowledge_post_tool_use(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": "s",
        "transcript_path": "/tmp/t",
        "cwd": str(REPO_ROOT),
        "permission_mode": "default",
        "agent_id": "a",
        "agent_type": "researcher",
        "hook_event_name": "PostToolUse",
        "tool_name": "mcp__knowledge__search",
        "tool_input": {"query": "q"},
        "tool_response": {"content": [{"type": "text", "text": json.dumps(payload)}]},
        "tool_use_id": "toolu-1",
    }


class TestFactGuard:
    _GOOD: ClassVar[dict[str, Any]] = {
        "doc": "d",
        "section": "s",
        "chip": "c",
        "version_range": "36.x",
        "hash": "h",
        "text": "fact",
    }
    _BAD: ClassVar[dict[str, Any]] = {"doc": "d", "text": "unprovenanced claim"}

    @pytest.mark.unit
    def test_provenance_predicate(self) -> None:
        assert has_provenance(self._GOOD)
        assert not has_provenance(self._BAD)

    @pytest.mark.unit
    def test_filter_strips_and_marks_unknown(self) -> None:
        clean, stripped = filter_chunks_payload({"chunks": [self._BAD]})
        assert stripped == 1
        assert clean["chunks"] == []
        assert clean["unknown"] is True

    @pytest.mark.unit
    def test_hook_passes_clean_output(self, hook_context: HookContext) -> None:
        result = asyncio.run(
            fact_guard(_knowledge_post_tool_use({"chunks": [self._GOOD]}), None, hook_context)
        )
        assert result == {}

    @pytest.mark.unit
    def test_hook_strips_unprovenanced_chunks(self, hook_context: HookContext) -> None:
        result = asyncio.run(
            fact_guard(
                _knowledge_post_tool_use({"chunks": [self._GOOD, self._BAD]}),
                None,
                hook_context,
            )
        )
        output = result["hookSpecificOutput"]
        assert "removed 1" in output["additionalContext"]
        updated = json.loads(output["updatedMCPToolOutput"]["content"][0]["text"])
        assert updated["chunks"] == [self._GOOD]

    @pytest.mark.unit
    def test_non_knowledge_tools_untouched(self, hook_context: HookContext) -> None:
        call = _knowledge_post_tool_use({"chunks": [self._BAD]})
        call["tool_name"] = "Bash"
        assert asyncio.run(fact_guard(call, None, hook_context)) == {}
