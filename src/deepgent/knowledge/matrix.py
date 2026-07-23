"""Compatibility-matrix reasoning engine (#14).

The matrix stores verified claims; this makes it *reason* over them:
transitive inference across API-compatible versions (with decayed confidence),
contradiction detection between claims, and active learning - which unverified
cell is most worth testing next. Pure functions over a claim set, so the
reasoning is unit-tested without the server.

A claim names a stack (component -> version) and a target component, and says
whether that component works, with a confidence in [0, 1]. Verified claims
carry confidence 1.0; inferences decay it.
"""

import json
from collections import deque
from dataclasses import dataclass, field

# component -> list of interchangeable version groups (e.g. ABI-compatible L4T
# point releases). Members of the same group substitute for one another.
CompatibilityRules = dict[str, list[frozenset[str]]]


@dataclass(frozen=True)
class Claim:
    """One compatibility claim about a target component on a stack."""

    stack: dict[str, str]
    component: str
    works: bool
    confidence: float = 1.0
    source: str = "verified"

    @property
    def key(self) -> tuple[tuple[str, str], ...]:
        return (*sorted(self.stack.items()), ("component", self.component))


@dataclass(frozen=True)
class Verdict:
    """The engine's answer for a queried cell."""

    works: bool | None
    confidence: float
    basis: str

    @property
    def known(self) -> bool:
        return self.works is not None


@dataclass(frozen=True)
class Contradiction:
    """Two verified claims about the same cell that disagree."""

    stack: dict[str, str]
    component: str

    def describe(self) -> str:
        stack = ", ".join(f"{k}={v}" for k, v in sorted(self.stack.items()))
        return f"{self.component} on ({stack}) has both pass and fail claims"


def load_claims(data: str) -> list[Claim]:
    """Parse a claims JSON array into Claim objects."""
    parsed = json.loads(data)
    claims: list[Claim] = []
    for item in parsed:
        claims.append(
            Claim(
                stack=dict(item["stack"]),
                component=str(item["component"]),
                works=bool(item["works"]),
                confidence=float(item.get("confidence", 1.0)),
                source=str(item.get("source", "verified")),
            )
        )
    return claims


def load_rules(data: str) -> CompatibilityRules:
    """Parse a rules JSON object {component: [[versions], ...]} into rules."""
    parsed = json.loads(data)
    return {
        component: [frozenset(group) for group in groups] for component, groups in parsed.items()
    }


def _groups_for(rules: CompatibilityRules, component: str) -> list[frozenset[str]]:
    return rules.get(component, [])


def _equiv_adjacency(rules: CompatibilityRules, component: str) -> dict[str, set[str]]:
    """Adjacency of the version-equivalence graph for a component.

    Each equivalence group is a clique; overlapping groups therefore connect,
    so equivalence is transitive across chained rules (36.4.3~36.4.4 and
    36.4.4~36.4.5 imply 36.4.3 reaches 36.4.5 in two hops).
    """
    adjacency: dict[str, set[str]] = {}
    for group in _groups_for(rules, component):
        members = list(group)
        for member in members:
            adjacency.setdefault(member, set()).update(m for m in members if m != member)
    return adjacency


def hop_distance(rules: CompatibilityRules, component: str, a: str, b: str) -> int | None:
    """Shortest number of equivalence hops from a to b, or None if unreachable.

    0 means the values are identical; 1 a direct rule; larger values a chain of
    interchangeable releases. Distance drives confidence decay, so a farther
    inference is trusted less.
    """
    if a == b:
        return 0
    adjacency = _equiv_adjacency(rules, component)
    if a not in adjacency:
        return None
    seen = {a}
    queue: deque[tuple[str, int]] = deque([(a, 0)])
    while queue:
        node, dist = queue.popleft()
        for neighbour in adjacency.get(node, ()):
            if neighbour == b:
                return dist + 1
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append((neighbour, dist + 1))
    return None


def _stack_applies(
    claim_stack: dict[str, str], query_stack: dict[str, str], rules: CompatibilityRules
) -> int | None:
    """Total equivalence hops if the claim applies to the query, else None.

    A claim applies when every component it names is reachable from the query's
    value under the rules. The return value is the summed hop distance across
    components (0 = an exact match on every component).
    """
    total_hops = 0
    for key, value in claim_stack.items():
        query_value = query_stack.get(key)
        if query_value is None:
            return None
        distance = hop_distance(rules, key, value, query_value)
        if distance is None:
            return None
        total_hops += distance
    return total_hops


def query(
    claims: list[Claim],
    stack: dict[str, str],
    component: str,
    rules: CompatibilityRules | None = None,
    decay: float = 0.7,
) -> Verdict:
    """Best verdict for a cell: direct claim if present, else best inference."""
    rules = rules or {}
    best: Verdict | None = None
    for claim in claims:
        if claim.component != component:
            continue
        hops = _stack_applies(claim.stack, stack, rules)
        if hops is None:
            continue
        if hops == 0:
            confidence = claim.confidence
            basis = f"verified ({claim.source})" if claim.confidence >= 1.0 else claim.source
        else:
            confidence = claim.confidence * (decay**hops)
            basis = f"inferred via {hops} version-equivalence hop(s)"
        candidate = Verdict(works=claim.works, confidence=confidence, basis=basis)
        if best is None or candidate.confidence > best.confidence:
            best = candidate
    return best if best is not None else Verdict(works=None, confidence=0.0, basis="no claim")


def detect_contradictions(claims: list[Claim]) -> list[Contradiction]:
    """Cells with both a passing and a failing verified (confidence 1.0) claim."""
    verdicts: dict[tuple[tuple[str, str], ...], set[bool]] = {}
    representative: dict[tuple[tuple[str, str], ...], Claim] = {}
    for claim in claims:
        if claim.confidence < 1.0:
            continue
        verdicts.setdefault(claim.key, set()).add(claim.works)
        representative[claim.key] = claim
    contradictions: list[Contradiction] = []
    for key, outcomes in verdicts.items():
        if len(outcomes) > 1:
            claim = representative[key]
            contradictions.append(Contradiction(stack=claim.stack, component=claim.component))
    return contradictions


@dataclass(frozen=True)
class VerifyCandidate:
    """An unverified cell ranked by how much testing it would resolve."""

    stack: dict[str, str]
    component: str
    value: float
    current_confidence: float


def next_to_verify(
    claims: list[Claim],
    universe: list[dict[str, str]],
    component: str,
    rules: CompatibilityRules | None = None,
    decay: float = 0.7,
) -> VerifyCandidate | None:
    """Highest-value unverified cell (active learning).

    Value rewards uncertainty (1 - current confidence) and connectivity (how
    many other universe cells this cell is version-interchangeable with, since
    verifying a well-connected cell propagates the most inference). Directly
    verified cells are skipped. Deterministic tie-break by stack string.
    """
    rules = rules or {}
    ranked: list[VerifyCandidate] = []
    for cell in universe:
        verdict = query(claims, cell, component, rules, decay)
        if verdict.basis.startswith("verified"):
            continue
        connectivity = sum(
            1
            for other in universe
            if other is not cell and _stack_applies(cell, other, rules) is not None
        )
        value = (1.0 - verdict.confidence) + 0.1 * connectivity
        ranked.append(
            VerifyCandidate(
                stack=cell,
                component=component,
                value=value,
                current_confidence=verdict.confidence,
            )
        )
    if not ranked:
        return None
    ranked.sort(key=lambda c: (-c.value, _stack_str(c.stack)))
    return ranked[0]


def _stack_str(stack: dict[str, str]) -> str:
    return ",".join(f"{k}={v}" for k, v in sorted(stack.items()))


@dataclass
class MatrixAnalysis:
    """Full reasoning pass over a claim set for a component."""

    component: str
    contradictions: list[Contradiction] = field(default_factory=list)
    next_verify: VerifyCandidate | None = None

    def render(self) -> str:
        lines = [f"# matrix analysis: {self.component}"]
        if self.contradictions:
            lines.append("contradictions:")
            lines += [f"  - {c.describe()}" for c in self.contradictions]
        else:
            lines.append("contradictions: none")
        if self.next_verify is not None:
            lines.append(
                f"next to verify: ({_stack_str(self.next_verify.stack)}) "
                f"[value {self.next_verify.value:.2f}, "
                f"current confidence {self.next_verify.current_confidence:.2f}]"
            )
        return "\n".join(lines) + "\n"


def analyze(
    claims: list[Claim],
    component: str,
    universe: list[dict[str, str]] | None = None,
    rules: CompatibilityRules | None = None,
) -> MatrixAnalysis:
    """Contradictions plus the next cell to verify for one component."""
    return MatrixAnalysis(
        component=component,
        contradictions=[c for c in detect_contradictions(claims) if c.component == component],
        next_verify=next_to_verify(claims, universe or [], component, rules) if universe else None,
    )
