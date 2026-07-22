"""Knowledge layer clients: datasheet RAG, compatibility matrix, failure
corpus, and skill pack fetch."""

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
    "RagClient",
    "SkillPack",
    "build_knowledge_server",
    "build_knowledge_tools",
    "build_rag_client",
    "default_skills_dir",
    "list_skills",
    "sync_skills",
]
