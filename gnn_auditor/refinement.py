"""Joint 1-WL refinement with injective full-signature interning, no digests."""

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from .data import Dataset, feature_key

Histogram = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Round:
    index: int
    palette: tuple[Any, ...]
    node_colors: tuple[tuple[int, ...], ...]
    histograms: tuple[Histogram, ...]


@dataclass(frozen=True)
class Refinement:
    rounds: tuple[Round, ...]

    @property
    def stable_histograms(self) -> tuple[Histogram, ...]:
        return self.rounds[-1].histograms


def _intern(signatures: list[Any]) -> tuple[tuple[int, ...], tuple[Any, ...]]:
    # Python dict/set uses hashes only as an index and resolves collisions by full
    # equality. The complete key, never a hash value, determines the color.
    palette = tuple(sorted(set(signatures)))
    colors = {signature: i for i, signature in enumerate(palette)}
    return tuple(colors[signature] for signature in signatures), palette


def _round(index: int, signatures: list[Any], sizes: list[int]) -> Round:
    flat_colors, palette = _intern(signatures)
    node_colors, offset = [], 0
    for size in sizes:
        node_colors.append(flat_colors[offset:offset + size])
        offset += size
    histograms = tuple(tuple(sorted(Counter(colors).items())) for colors in node_colors)
    return Round(index, palette, tuple(node_colors), histograms)


def refine(dataset: Dataset, *, on_round: Callable[[Round], None] | None = None) -> Refinement:
    """Run to a stable partition on the whole disjoint union, with a shared palette.

    No iteration cap: a non-splitting round is required, even if all graphs are
    already separated. A round retains the old color, so classes cannot merge.
    """
    sizes = [len(g.node_ids) for g in dataset.graphs]
    rounds = [_round(0, [feature_key(x) for g in dataset.graphs for x in g.features], sizes)]
    if on_round:
        on_round(rounds[0])
    while True:
        previous = rounds[-1]
        signatures = []
        for graph, colors in zip(dataset.graphs, previous.node_colors):
            for v, neighbors in enumerate(graph.adjacency):
                multiset = tuple(sorted(Counter(colors[u] for u in neighbors).items()))
                signatures.append((colors[v], multiset))
        current = _round(previous.index + 1, signatures, sizes)
        rounds.append(current)
        if on_round:
            on_round(current)
        assert len(current.palette) >= len(previous.palette), "retained colors cannot merge"
        if len(current.palette) == len(previous.palette):
            return Refinement(tuple(rounds))
