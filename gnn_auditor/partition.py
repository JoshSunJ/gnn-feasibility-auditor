"""Exact worklist color refinement with compact, justified split evidence.

Cell IDs are local palette labels, never hashes. No capped partial result is
returned. A summary proof records smaller moved groups rather than all rounds.
"""

from collections import Counter, defaultdict, deque
from dataclasses import dataclass

from .data import Dataset, feature_key
from .report import build_class_report


@dataclass(frozen=True)
class Partition:
    node_colors: tuple[tuple[int, ...], ...]
    histograms: tuple
    events: tuple
    initial_color_count: int
    final_color_count: int
    processed_splitters: int
    edge_visits: int
    moved_vertices: int


def refine_partition(dataset: Dataset, *, on_step=None) -> Partition:
    sizes = [len(g.node_ids) for g in dataset.graphs]
    adjacency, keys = [], []
    offset = 0
    for graph in dataset.graphs:
        adjacency.extend(tuple(offset + u for u in neighbors) for neighbors in graph.adjacency)
        keys.extend(feature_key(x) for x in graph.features)
        offset += len(graph.node_ids)
    palette = sorted(set(keys))
    initial_count = len(palette)
    initial_ids = {key: i for i, key in enumerate(palette)}
    cells = [set() for _ in palette]
    owners = []
    for v, key in enumerate(keys):
        color = initial_ids[key]
        cells[color].add(v)
        owners.append(color)
    queue = deque(range(initial_count))
    pending = set(queue)
    events = []
    processed = visits = moved = 0
    while queue:
        splitter = queue.popleft()
        pending.remove(splitter)
        counts = Counter()
        # Count the splitter before mutating any cell, including itself.
        for v in cells[splitter]:
            for u in adjacency[v]:
                counts[u] += 1
                visits += 1
        affected = defaultdict(lambda: defaultdict(list))
        for v, count in counts.items():
            affected[owners[v]][count].append(v)
        changes = []
        for color in sorted(affected):
            positive = affected[color]
            positive_size = sum(len(vertices) for vertices in positive.values())
            zero_size = len(cells[color]) - positive_size
            group_sizes = {count: len(vertices) for count, vertices in positive.items()}
            if zero_size:
                group_sizes[0] = zero_size
            if len(group_sizes) <= 1:
                continue
            # Ties use counts, not vertex IDs. The largest group stays put.
            retained = min(group_sizes, key=lambda count: (-group_sizes[count], count))
            groups = dict(positive)
            if zero_size and retained != 0:
                local_positive = {v for vertices in positive.values() for v in vertices}
                groups[0] = list(cells[color].difference(local_positive))
            moved_groups = []
            for count in sorted(groups):
                if count == retained:
                    continue
                vertices = groups[count]
                new_color = len(cells)
                cells.append(set(vertices))
                cells[color].difference_update(vertices)
                for v in vertices:
                    owners[v] = new_color
                moved += len(vertices)
                queue.append(new_color)
                pending.add(new_color)
                moved_groups.append({"count": count, "vertices": vertices})
            changes.append({"cell": color, "retained_count": retained, "moved": moved_groups})
        if changes:
            events.append({"splitter": splitter, "splits": changes})
        processed += 1
        if on_step:
            on_step({"processed_splitters": processed, "color_count": len(cells),
                     "edge_visits": visits, "moved_vertices": moved})
    colors = []
    offset = 0
    for size in sizes:
        colors.append(tuple(owners[offset:offset + size]))
        offset += size
    histograms = tuple(tuple(sorted(Counter(row).items())) for row in colors)
    return Partition(tuple(colors), histograms, tuple(events), initial_count, len(cells), processed, visits, moved)


def partition_report(dataset: Dataset, result: Partition, max_pairs=20, include_certificate=False):
    report = build_class_report(dataset, result.histograms, max_pairs)
    report.update({"report_version": 2, "method": "exact_partition_1wl_to_equitable",
                   "initial_color_count": result.initial_color_count, "final_color_count": result.final_color_count,
                   "split_count": sum(len(e["splits"]) for e in result.events),
                   "producer_work": {"processed_splitters": result.processed_splitters, "edge_visits": result.edge_visits,
                            "moved_vertices": result.moved_vertices},
                   "trace_mode": "compact_justified_splits; no synchronous round trace"})
    by_id = {g.id: i for i, g in enumerate(dataset.graphs)}
    for witness in report["conflict_witnesses"]:
        witness["matching_stable_histogram"] = [list(x) for x in result.histograms[by_id[witness["graph_a"]]]]
    if include_certificate:
        report["certificate"] = {"version": 2, "graph_order": [g.id for g in dataset.graphs],
                                 "node_order": [list(g.node_ids) for g in dataset.graphs],
                                 "events": result.events, "final_node_colors": result.node_colors}
    return report


def audit_partition(dataset: Dataset, max_pairs=20, include_certificate=False, *, on_step=None):
    result = refine_partition(dataset, on_step=on_step)
    return partition_report(dataset, result, max_pairs, include_certificate)
