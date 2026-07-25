"""Seeding the matrix from versions.toml."""

from pathlib import Path

from deepgent_server.knowledge import KnowledgeStore
from deepgent_server.seed import seed_from_versions

_VERSIONS = Path(__file__).resolve().parents[2] / "versions.toml"


def test_seed_writes_anchored_pairwise_claims(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "k.db")
    ids = seed_from_versions(store, _VERSIONS)

    # One claim per non-anchor component across the jp6 and jp7 lines.
    assert len(ids) == store.claim_count() == 9

    # A query naming the L4T anchor plus a component resolves with provenance.
    claim = store.query_claim({"l4t": "36.4.3", "tensorrt": "10.3"})
    assert claim is not None
    assert claim.status == "verified_pass"
    assert claim.evidence_run_id == "versions.toml:jetson.jp6"

    # A cross-line pairing (jp7 TensorRT on the jp6 platform) is not claimed.
    assert store.query_claim({"l4t": "36.4.3", "tensorrt": "10.16.2"}) is None


def test_seed_claims_name_only_two_keys(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "k.db")
    seed_from_versions(store, _VERSIONS)
    # Every seeded claim pairs the anchor with exactly one component, so broad
    # queries can resolve it (a full-stack claim would need an exact match).
    claim = store.query_claim({"l4t": "36.4.3", "cuda": "12.6"})
    assert claim is not None
    assert set(claim.stack) == {"l4t", "cuda"}
