"""Training ceiling and explicit conflict witnesses from exact WL classes."""

from collections import Counter
from fractions import Fraction
from itertools import combinations

from .data import Dataset, label_key
from .refinement import Refinement, refine

LIMITATIONS = [
    "This is an upper bound on micro accuracy for the supplied training multiset, not a prediction of test accuracy.",
    "Applies to deterministic shared message passing and invariant multiset readout using only the supplied topology and actual features.",
    "Matching complete stable color histograms proves 1-WL indistinguishability, not graph isomorphism. No graph hash is used as proof.",
    "A particular architecture, depth or optimizer can perform below this ceiling. A 100% ceiling is inconclusive.",
    "Export all actual model inputs after preprocessing in the declared precision; extra inputs, stochastic evaluation or numerical artifacts can invalidate the model comparison.",
]


def build_report(dataset: Dataset, result: Refinement, max_pairs: int = 20) -> dict:
    if type(max_pairs) is not int or max_pairs < 0:
        raise ValueError("max_pairs must be a nonnegative integer")
    grouped = {}
    for i, histogram in enumerate(result.stable_histograms):
        grouped.setdefault(histogram, []).append(i)
    # Membership order is independent of input graph order; color IDs are local.
    groups = sorted(grouped.items(), key=lambda item: tuple(sorted(dataset.graphs[i].id for i in item[1])))
    classes, witnesses, correct = [], [], 0
    indistinguishable_pairs, conflict_pairs = 0, 0
    for k, (histogram, indices) in enumerate(groups):
        indices = sorted(indices, key=lambda i: dataset.graphs[i].id)
        counts = Counter(label_key(dataset.graphs[i].label) for i in indices)
        majority = max(counts.values())
        correct += majority
        size = len(indices)
        all_pairs = size * (size - 1) // 2
        conflicts = all_pairs - sum(n * (n - 1) // 2 for n in counts.values())
        indistinguishable_pairs += all_pairs
        conflict_pairs += conflicts
        cid = f"C{k + 1}"
        classes.append({
            "id": cid, "graph_ids": [dataset.graphs[i].id for i in indices],
            "size": size, "stable_histogram": [list(x) for x in histogram],
            "label_counts": [{"label_type": kind, "label": label, "count": n}
                             for (kind, label), n in sorted(counts.items())],
            "majority_labels": [{"label_type": kind, "label": label}
                                for (kind, label), n in sorted(counts.items()) if n == majority],
            "max_correct": majority, "unavoidable_errors": size - majority,
            "conflicting_pair_count": conflicts,
        })
        # Enumerate only requested witnesses, never materialize all O(N^2) pairs.
        if len(witnesses) < max_pairs and conflicts:
            for a, b in combinations(indices, 2):
                ga, gb = dataset.graphs[a], dataset.graphs[b]
                if label_key(ga.label) == label_key(gb.label):
                    continue
                witnesses.append({"class_id": cid, "graph_a": ga.id, "label_a": ga.label,
                                  "graph_b": gb.id, "label_b": gb.label,
                                  "matching_histograms_by_round": [[list(x) for x in r.histograms[a]] for r in result.rounds]})
                if len(witnesses) == max_pairs:
                    break
    total = len(dataset.graphs)
    fraction = Fraction(correct, total)
    return {
        "report_version": 1, "method": "exact_joint_1wl_to_stability", "split": "train",
        "feature_dtype": dataset.feature_dtype, "feature_dim": dataset.feature_dim,
        "feature_equality": "exact represented IEEE values; signed zeros equal; no tolerance or binning",
        "graph_count": total, "node_count": sum(len(g.node_ids) for g in dataset.graphs),
        "edge_count": sum(len(g.edges) for g in dataset.graphs), "class_count": len(classes),
        "stabilization_round": result.rounds[-1].index,
        "rounds": [{"round": r.index, "color_count": len(r.palette)} for r in result.rounds],
        "training_accuracy_upper_bound": {"max_correct": correct, "total": total,
                                          "fraction": str(fraction), "value": correct / total},
        "unavoidable_training_errors": total - correct,
        "indistinguishable_pair_count": indistinguishable_pairs,
        "conflicting_pair_count": conflict_pairs,
        "conflict_witnesses_shown": len(witnesses),
        "conflict_witnesses_omitted": conflict_pairs - len(witnesses),
        "classes": classes, "conflict_witnesses": witnesses, "limitations": LIMITATIONS,
    }


def certificate(dataset: Dataset, result: Refinement) -> dict:
    return {"version": 1, "graph_order": [g.id for g in dataset.graphs],
            "node_order": [list(g.node_ids) for g in dataset.graphs],
            "rounds": [{"round": r.index, "palette": r.palette, "node_colors": r.node_colors,
                        "histograms": r.histograms} for r in result.rounds]}


def audit(dataset: Dataset, max_pairs: int = 20, include_certificate: bool = False) -> dict:
    result = refine(dataset)
    report = build_report(dataset, result, max_pairs)
    if include_certificate:
        report["certificate"] = certificate(dataset, result)
    return report


def text_report(report: dict) -> str:
    bound = report["training_accuracy_upper_bound"]
    lines = ["GNN Feasibility Auditor — exact feature-aware 1-WL",
             f"Training accuracy upper bound: {bound['max_correct']}/{bound['total']} = {100 * bound['value']:.2f}%",
             f"Unavoidable training errors: {report['unavoidable_training_errors']}",
             f"Graphs: {report['graph_count']} | WL classes: {report['class_count']} | Stable at round: {report['stabilization_round']}",
             f"Features: {report['feature_dim']}D {report['feature_dtype']} (exact represented values)",
             f"Indistinguishable pairs: {report['indistinguishable_pair_count']} | Cross-label pairs: {report['conflicting_pair_count']}",
             "", "Conflicting equivalence classes:"]
    for item in report["classes"]:
        if not item["unavoidable_errors"]:
            continue
        labels = ", ".join(f"{x['label']!r} ({x['label_type']}): {x['count']}" for x in item["label_counts"])
        lines.extend([f"  {item['id']}: {', '.join(item['graph_ids'])}",
                      f"    Labels: {labels}; at most {item['max_correct']}/{item['size']} correct"])
    if not report["conflicting_pair_count"]:
        lines.append("  None. A 100% ceiling is inconclusive about model trainability.")
    lines.extend(["", "Concrete cross-label witnesses:"])
    for pair in report["conflict_witnesses"]:
        lines.append(f"  {pair['graph_a']} ({pair['label_a']!r}) <-> {pair['graph_b']} ({pair['label_b']!r}) [{pair['class_id']}]")
        lines.append("    Matching exact color histograms in rounds " + ", ".join(map(str, range(len(pair['matching_histograms_by_round'])))))
    if report["conflict_witnesses_omitted"]:
        lines.append(f"  {report['conflict_witnesses_omitted']} further witness pairs omitted; all class memberships are included.")
    lines.extend(["", *report["limitations"]])
    return "\n".join(lines) + "\n"
