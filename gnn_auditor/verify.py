"""Independent certificate replay; deliberately does not call the refinement engine."""

from collections import Counter
from fractions import Fraction
from itertools import groupby
from typing import Any

from .data import Dataset, feature_key, label_key


class VerificationError(ValueError):
    pass


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _freeze(value: Any) -> Any:
    return tuple(_freeze(x) for x in value) if isinstance(value, (list, tuple)) else value


def verify_report(dataset: Dataset, report: dict) -> None:
    """Validate a report against the given actual inputs, or raise VerificationError."""
    if isinstance(report, dict) and report.get("report_version") == 2:
        from .partition_verify import verify_partition_report
        verify_partition_report(dataset, report)
        return
    try:
        _verify(dataset, report)
    except VerificationError:
        raise
    except (KeyError, TypeError, IndexError, ValueError, OverflowError, RecursionError) as error:
        raise VerificationError(f"malformed certificate/report: {error}") from error


def _verify(dataset: Dataset, report: dict) -> None:
    cert = report["certificate"]
    _check(cert["version"] == 1 and report["report_version"] == 1, "unsupported version")
    _check(report["method"] == "exact_joint_1wl_to_stability" and report["split"] == "train", "wrong method or split")
    _check(report["feature_dtype"] == dataset.feature_dtype and report["feature_dim"] == dataset.feature_dim, "feature contract mismatch")
    _check(cert["graph_order"] == [g.id for g in dataset.graphs], "graph order mismatch")
    _check(cert["node_order"] == [list(g.node_ids) for g in dataset.graphs], "node order mismatch")
    rounds = cert["rounds"]
    node_total = sum(len(g.node_ids) for g in dataset.graphs)
    _check(2 <= len(rounds) <= node_total + 2, "invalid number of refinement rounds")
    previous, previous_count = None, None
    traces, statistics = [], []
    for t, item in enumerate(rounds):
        _check(item["round"] == t, "nonconsecutive round indices")
        palette = _freeze(item["palette"])
        _check(len(set(palette)) == len(palette), f"round {t}: palette is not injective")
        colors = _freeze(item["node_colors"])
        _check(len(colors) == len(dataset.graphs), f"round {t}: graph count mismatch")
        used = set()
        histograms = []
        for i, graph in enumerate(dataset.graphs):
            _check(len(colors[i]) == len(graph.node_ids), f"round {t}: node count mismatch")
            for v, color in enumerate(colors[i]):
                _check(type(color) is int and 0 <= color < len(palette), f"round {t}: invalid color")
                used.add(color)
                if t == 0:
                    expected = feature_key(graph.features[v])
                else:
                    neighbors = sorted(previous[i][u] for u in graph.adjacency[v])
                    counts = tuple((c, sum(1 for _ in group)) for c, group in groupby(neighbors))
                    expected = (previous[i][v], counts)
                _check(palette[color] == expected, f"round {t}, graph {graph.id!r}, node {graph.node_ids[v]!r}: signature mismatch")
            histograms.append(tuple(sorted(Counter(colors[i]).items())))
        _check(used == set(range(len(palette))), f"round {t}: unused palette entries")
        histograms = tuple(histograms)
        _check(_freeze(item["histograms"]) == histograms, f"round {t}: histogram mismatch")
        if t:
            _check(len(palette) >= previous_count, f"round {t}: colors merged")
            if t == len(rounds) - 1:
                _check(len(palette) == previous_count, "certificate stops before stabilization")
            else:
                _check(len(palette) > previous_count, "certificate continues after stabilization")
        traces.append(histograms)
        statistics.append({"round": t, "color_count": len(palette)})
        previous, previous_count = colors, len(palette)
    _check(report["rounds"] == statistics, "round statistics mismatch")
    _check(report["stabilization_round"] == len(rounds) - 1, "stabilization round mismatch")
    _check(report["node_count"] == node_total, "total node count mismatch")
    _check(report["edge_count"] == sum(len(g.edges) for g in dataset.graphs), "total edge count mismatch")

    groups = {}
    for graph, histogram in zip(dataset.graphs, traces[-1]):
        groups.setdefault(histogram, []).append(graph)
    expected_groups = {frozenset(g.id for g in group): (hist, group) for hist, group in groups.items()}
    classes = report["classes"]
    _check(len(classes) == len(groups) == report["class_count"], "class count mismatch")
    seen, class_for = set(), {}
    correct, conflicts, all_pairs = 0, 0, 0
    class_ids = set()
    for item in classes:
        members = frozenset(item["graph_ids"])
        _check(len(members) == len(item["graph_ids"]), "duplicate class members")
        _check(members in expected_groups and members not in seen, "incorrect equivalence class")
        seen.add(members)
        cid = item["id"]
        _check(isinstance(cid, str) and cid not in class_ids, "duplicate or invalid class ID")
        class_ids.add(cid)
        for gid in members:
            class_for[gid] = cid
        histogram, graphs = expected_groups[members]
        counts = Counter(label_key(g.label) for g in graphs)
        label_counts = [{"label_type": kind, "label": label, "count": n} for (kind, label), n in sorted(counts.items())]
        majority = max(counts.values())
        majority_labels = [{"label_type": kind, "label": label} for (kind, label), n in sorted(counts.items()) if n == majority]
        size = len(graphs)
        pairs = size * (size - 1) // 2
        cross = pairs - sum(n * (n - 1) // 2 for n in counts.values())
        _check(_freeze(item["stable_histogram"]) == histogram, "class histogram mismatch")
        _check(item["label_counts"] == label_counts and item["majority_labels"] == majority_labels, "label counts/majorities mismatch")
        _check(item["size"] == size and item["max_correct"] == majority and item["unavoidable_errors"] == size - majority, "class bound mismatch")
        _check(item["conflicting_pair_count"] == cross, "class conflict count mismatch")
        correct += majority
        conflicts += cross
        all_pairs += pairs
    total = len(dataset.graphs)
    expected_bound = {"max_correct": correct, "total": total, "fraction": str(Fraction(correct, total)), "value": correct / total}
    _check(report["graph_count"] == total and report["training_accuracy_upper_bound"] == expected_bound, "training ceiling mismatch")
    _check(report["unavoidable_training_errors"] == total - correct, "error count mismatch")
    _check(report["conflicting_pair_count"] == conflicts and report["indistinguishable_pair_count"] == all_pairs, "pair count mismatch")
    by_id = {g.id: (i, g) for i, g in enumerate(dataset.graphs)}
    witnesses = report["conflict_witnesses"]
    _check(report["conflict_witnesses_shown"] == len(witnesses) and report["conflict_witnesses_omitted"] == conflicts - len(witnesses), "witness counts mismatch")
    witnessed = set()
    for pair in witnesses:
        a, ga = by_id[pair["graph_a"]]
        b, gb = by_id[pair["graph_b"]]
        key = frozenset((ga.id, gb.id))
        _check(len(key) == 2 and key not in witnessed, "duplicate or self witness")
        witnessed.add(key)
        _check(label_key(ga.label) != label_key(gb.label), "witness labels are equal")
        _check(pair["label_a"] == ga.label and type(pair["label_a"]) is type(ga.label) and pair["label_b"] == gb.label and type(pair["label_b"]) is type(gb.label), "witness labels mismatch")
        _check(class_for[ga.id] == class_for[gb.id] == pair["class_id"], "witness class mismatch")
        _check(all(trace[a] == trace[b] for trace in traces), "witness separates under WL")
        _check(_freeze(pair["matching_histograms_by_round"]) == tuple(trace[a] for trace in traces), "witness trace mismatch")
