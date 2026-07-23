"""Knowledge layer clients: datasheet RAG, compatibility matrix, failure
corpus, and skill pack fetch."""

from deepgent.knowledge.errata import ErrataScanResult, Erratum, scan_errata
from deepgent.knowledge.matrix import (
    Claim,
    Contradiction,
    MatrixAnalysis,
    Verdict,
    VerifyCandidate,
    analyze,
    detect_contradictions,
    next_to_verify,
    query,
)
from deepgent.knowledge.products import (
    BomCandidate,
    BomConstraints,
    TriageResult,
    UpgradeReport,
    bom_advise,
    triage,
    upgrade_check,
)
from deepgent.knowledge.rag import (
    PROVENANCE_FIELDS,
    RagClient,
    build_knowledge_server,
    build_knowledge_tools,
    build_rag_client,
)
from deepgent.knowledge.skills import (
    SkillPack,
    default_skills_dir,
    list_skills,
    sync_skills,
)

__all__ = [
    "PROVENANCE_FIELDS",
    "BomCandidate",
    "BomConstraints",
    "Claim",
    "Contradiction",
    "ErrataScanResult",
    "Erratum",
    "MatrixAnalysis",
    "RagClient",
    "SkillPack",
    "TriageResult",
    "UpgradeReport",
    "Verdict",
    "VerifyCandidate",
    "analyze",
    "bom_advise",
    "build_knowledge_server",
    "build_knowledge_tools",
    "build_rag_client",
    "default_skills_dir",
    "detect_contradictions",
    "list_skills",
    "next_to_verify",
    "query",
    "scan_errata",
    "sync_skills",
    "triage",
    "upgrade_check",
]
