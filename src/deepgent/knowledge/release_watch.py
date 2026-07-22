"""Release watch: detect upstream versions newer than versions.toml.

v0 checks the NVIDIA container registry for l4t-jetpack tags newer than the
pinned jp6 l4t_container. The scheduled workflow surfaces findings as a
repository issue; a human lands the versions.toml bump so the full golden
suite gates it (section 13 rule). ROS feed checks arrive later.
"""

import re
from dataclasses import dataclass

import httpx
import structlog

from deepgent.errors import KnowledgeError

_logger = structlog.get_logger(__name__)

NVCR_AUTH_URL = "https://nvcr.io/proxy_auth?scope=repository:nvidia/l4t-jetpack:pull"
NVCR_TAGS_URL = "https://nvcr.io/v2/nvidia/l4t-jetpack/tags/list"
_TAG = re.compile(r"^r(\d+)\.(\d+)(?:\.(\d+))?$")
_TIMEOUT_S = 20.0


@dataclass(frozen=True)
class ReleaseFinding:
    """One newer upstream artifact than the pinned version."""

    component: str
    pinned: str
    newest: str

    def describe(self) -> str:
        return f"{self.component}: pinned {self.pinned}, upstream has {self.newest}"


def tag_key(tag: str) -> tuple[int, int, int] | None:
    match = _TAG.match(tag)
    if match is None:
        return None
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3) or 0),
    )


def newer_l4t_tags(pinned: str, tags: list[str]) -> list[str]:
    """Tags strictly newer than the pinned l4t_container tag, sorted."""
    pinned_key = tag_key(pinned)
    if pinned_key is None:
        raise KnowledgeError(f"pinned l4t_container '{pinned}' is not an rX.Y[.Z] tag")
    newer = [tag for tag in tags if (key := tag_key(tag)) is not None and key > pinned_key]
    return sorted(newer, key=lambda tag: tag_key(tag) or (0, 0, 0))


def fetch_l4t_tags() -> list[str]:
    """List public l4t-jetpack tags from nvcr.io (anonymous pull token)."""
    try:
        with httpx.Client(timeout=_TIMEOUT_S) as client:
            token = client.get(NVCR_AUTH_URL).json()["token"]
            response = client.get(NVCR_TAGS_URL, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            tags: list[str] = response.json()["tags"]
            return tags
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise KnowledgeError(f"cannot list nvcr.io l4t-jetpack tags: {exc}") from exc


def check_releases(pinned_l4t_container: str) -> list[ReleaseFinding]:
    """All findings for the current pins; empty means fully current."""
    newer = newer_l4t_tags(pinned_l4t_container, fetch_l4t_tags())
    if not newer:
        return []
    return [
        ReleaseFinding(
            component="nvcr.io/nvidia/l4t-jetpack",
            pinned=pinned_l4t_container,
            newest=newer[-1],
        )
    ]
