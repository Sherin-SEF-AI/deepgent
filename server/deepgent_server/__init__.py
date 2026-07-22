"""deepgent knowledge API server (Phase 3+): datasheet RAG v0.

Separate deploy from the client package; proprietary per CLAUDE.md section
21. Every request is authenticated; there are no anonymous reads and no
bulk export endpoints (section 19).
"""

__all__ = ["create_app"]

from deepgent_server.app import create_app
