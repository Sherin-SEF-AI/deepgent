"""Knowledge layer clients: datasheet RAG, compatibility matrix, failure
corpus, and skill pack fetch."""

from deepgent.knowledge.errata import ErrataScanResult, Erratum, scan_errata
from deepgent.knowledge.fact_confidence import (
    ArbitratedFact,
    ArbitrationReport,
    FactAssertion,
    arbitrate,
    arbitrate_all,
    confidence_for,
)
from deepgent.knowledge.hardware_check import (
    ConflictReport,
    HardwareConfig,
    Peripheral,
    Rail,
    check_conflicts,
    load_config,
)
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
from deepgent.knowledge.premortem import (
    PredictedRisk,
    PreMortem,
    assemble_premortem,
    premortem,
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
    "ArbitratedFact",
    "ArbitrationReport",
    "BomCandidate",
    "BomConstraints",
    "Claim",
    "ConflictReport",
    "Contradiction",
    "ErrataScanResult",
    "Erratum",
    "FactAssertion",
    "HardwareConfig",
    "MatrixAnalysis",
    "Peripheral",
    "PreMortem",
    "PredictedRisk",
    "RagClient",
    "Rail",
    "SkillPack",
    "TriageResult",
    "UpgradeReport",
    "Verdict",
    "VerifyCandidate",
    "analyze",
    "arbitrate",
    "arbitrate_all",
    "assemble_premortem",
    "bom_advise",
    "build_knowledge_server",
    "build_knowledge_tools",
    "build_rag_client",
    "check_conflicts",
    "confidence_for",
    "default_skills_dir",
    "detect_contradictions",
    "list_skills",
    "load_config",
    "next_to_verify",
    "premortem",
    "query",
    "scan_errata",
    "sync_skills",
    "triage",
    "upgrade_check",
]
