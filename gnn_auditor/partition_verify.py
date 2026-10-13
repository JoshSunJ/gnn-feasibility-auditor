"""Independent justified-split replay plus final equitability and report checks.

Does not import or call the partition producer. Arbitrary stable partitions are
insufficient: every split must be forced by exact counts into an existing cell.
"""

from collections import Counter, defaultdict
from fractions import Fraction

from .data import feature_key, label_key
from .verify import VerificationError


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def verify_partition_report(dataset, report):
    try:
        _replay(dataset, report)
    except VerificationError:
        raise
    except (KeyError, ValueError, TypeError, IndexError, OverflowError, RecursionError) as error:
        raise VerificationError(f"malformed partition certificate: {error}") from error


def _replay(dataset, report):
    require(report["report_version"] == 2 and report["method"] == "exact_partition_1wl_to_equitable", "wrong summary method")
    require(report["split"] == "train", "wrong training split")
    require(report["feature_dtype"] == dataset.feature_dtype and report["feature_dim"] == dataset.feature_dim, "feature contract mismatch")
    cert = report["certificate"]
    require(cert["version"] == 2, "wrong certificate version")
    require(cert["graph_order"] == [g.id for g in dataset.graphs] and cert["node_order"] == [list(g.node_ids) for g in dataset.graphs], "input order mismatch")
    adjacency, initial = [], []
    start = 0
    for graph in dataset.graphs:
        for neighbors in graph.adjacency:
            adjacency.append([start + neighbor for neighbor in neighbors])
        initial.extend(feature_key(vector) for vector in graph.features)
        start += len(graph.node_ids)
    unique = sorted(set(initial))
    initial_index = {value: i for i, value in enumerate(unique)}
    cells = [set() for _ in unique]
    owner = [initial_index[value] for value in initial]
    for vertex, color in enumerate(owner):
        cells[color].add(vertex)
    require(report["initial_color_count"] == len(unique), "initial palette count mismatch")
    splits = 0
    for step, event in enumerate(cert["events"]):
        splitter = event["splitter"]
        require(type(splitter) is int and 0 <= splitter < len(cells), f"step {step}: invalid splitter")
        counts = {}
        for vertex in cells[splitter]:
            for neighbor in adjacency[vertex]:
                counts[neighbor] = counts.get(neighbor, 0) + 1
        by_cell = defaultdict(list)
        for vertex, count in counts.items():
            by_cell[owner[vertex]].append((vertex, count))
        original_cell_count = len(cells)
        seen_cells = set()
        require(isinstance(event["splits"], list) or isinstance(event["splits"], tuple), "split list required")
        require(bool(event["splits"]), "empty proof event")
        for change in event["splits"]:
            color = change["cell"]
            require(type(color) is int and 0 <= color < original_cell_count and color not in seen_cells, "duplicate or invalid split cell")
            seen_cells.add(color)
            groups = defaultdict(set)
            for vertex, count in by_cell[color]:
                groups[count].add(vertex)
            touched = set().union(*groups.values()) if groups else set()
            zero_size = len(cells[color]) - len(touched)
            sizes = {count: len(vertices) for count, vertices in groups.items()}
            if zero_size:
                sizes[0] = zero_size
            retained = change["retained_count"]
            require(type(retained) is int and retained in sizes and len(sizes) > 1, "split is not forced by neighbor counts")
            seen_counts, moved = set(), set()
            allocated = []
            for part in change["moved"]:
                count, sequence = part["count"], part["vertices"]
                require(type(count) is int and count in sizes and count != retained and count not in seen_counts, "invalid moved count group")
                seen_counts.add(count)
                require(all(type(v) is int for v in sequence), "vertex positions must be integers")
                vertices = set(sequence)
                require(len(vertices) == len(sequence) and bool(vertices) and vertices <= cells[color] and not vertices & moved, "missing, duplicate or invented vertices")
                expected = cells[color] - touched if count == 0 else groups[count]
                require(vertices == expected, "moved vertices do not form a complete justified group")
                moved.update(vertices)
                allocated.append(vertices)
            require(seen_counts == set(sizes) - {retained}, "omitted neighbor-count group")
            require(len(cells[color]) - len(moved) == sizes[retained] > 0, "wrong retained group")
            cells[color].difference_update(moved)
            for vertices in allocated:
                new_color = len(cells)
                cells.append(vertices)
                for vertex in vertices:
                    owner[vertex] = new_color
            splits += 1
    require(report["split_count"] == splits and report["final_color_count"] == len(cells), "partition statistics mismatch")
    # Equitability is checked with full independently expanded neighbor colors.
    signature_for = {}
    for vertex, neighbors in enumerate(adjacency):
        signature = tuple(sorted(Counter(owner[u] for u in neighbors).items()))
        color = owner[vertex]
        if color in signature_for:
            require(signature_for[color] == signature, "certificate stops before equitable stability")
        else:
            signature_for[color] = signature
    final_rows, histograms, offset = [], [], 0
    for graph in dataset.graphs:
        row = owner[offset:offset + len(graph.node_ids)]
        offset += len(graph.node_ids)
        final_rows.append(row)
        histograms.append(tuple(sorted(Counter(row).items())))
    require(all(type(color) is int for row in cert["final_node_colors"] for color in row), "final colors must be integers")
    require(cert["final_node_colors"] == final_rows or tuple(tuple(row) for row in cert["final_node_colors"]) == tuple(tuple(row) for row in final_rows), "final colors mismatch")
    groups = defaultdict(list)
    for graph, histogram in zip(dataset.graphs, histograms):
        groups[histogram].append(graph)
    expected_members = {frozenset(g.id for g in group): (histogram, group) for histogram, group in groups.items()}
    require(report["class_count"] == len(groups) == len(report["classes"]), "equivalence class count mismatch")
    seen, class_ids, class_for = set(), set(), {}
    correct = conflicts = indistinguishable = 0
    for item in report["classes"]:
        members = frozenset(item["graph_ids"])
        require(len(members) == len(item["graph_ids"]) and members in expected_members and members not in seen, "wrong class membership")
        seen.add(members)
        cid = item["id"]
        require(isinstance(cid, str) and cid not in class_ids, "duplicate class identifier")
        class_ids.add(cid)
        class_for.update({gid: cid for gid in members})
        histogram, graphs = expected_members[members]
        labels = Counter(label_key(g.label) for g in graphs)
        majority = max(labels.values())
        expected_counts = [{"label_type": kind, "label": label, "count": n} for (kind, label), n in sorted(labels.items())]
        expected_majorities = [{"label_type": kind, "label": label} for (kind, label), n in sorted(labels.items()) if n == majority]
        size = len(graphs)
        pairs = size * (size - 1) // 2
        cross = pairs - sum(n * (n - 1) // 2 for n in labels.values())
        require(tuple(tuple(x) for x in item["stable_histogram"]) == histogram, "wrong class histogram")
        require(item["label_counts"] == expected_counts and item["majority_labels"] == expected_majorities, "wrong class labels")
        require(item["size"] == size and item["max_correct"] == majority and item["unavoidable_errors"] == size - majority and item["conflicting_pair_count"] == cross, "wrong class arithmetic")
        correct += majority
        conflicts += cross
        indistinguishable += pairs
    total = len(dataset.graphs)
    bound = {"max_correct": correct, "total": total, "fraction": str(Fraction(correct, total)), "value": correct / total}
    require(report["graph_count"] == total and report["node_count"] == len(owner) and report["edge_count"] == sum(len(g.edges) for g in dataset.graphs), "input totals mismatch")
    require(report["training_accuracy_upper_bound"] == bound and report["unavoidable_training_errors"] == total - correct, "wrong ceiling")
    require(report["conflicting_pair_count"] == conflicts and report["indistinguishable_pair_count"] == indistinguishable, "wrong pair counts")
    by_id = {g.id: (i, g) for i, g in enumerate(dataset.graphs)}
    witnesses = report["conflict_witnesses"]
    require(report["conflict_witnesses_shown"] == len(witnesses) and report["conflict_witnesses_omitted"] == conflicts - len(witnesses), "wrong witness count")
    seen_pairs = set()
    for pair in witnesses:
        a, ga = by_id[pair["graph_a"]]
        b, gb = by_id[pair["graph_b"]]
        key = frozenset((ga.id, gb.id))
        require(len(key) == 2 and key not in seen_pairs and label_key(ga.label) != label_key(gb.label), "invalid witness")
        seen_pairs.add(key)
        require(class_for[ga.id] == class_for[gb.id] == pair["class_id"] and histograms[a] == histograms[b], "witness separates under 1-WL")
        require(label_key(pair["label_a"]) == label_key(ga.label) and label_key(pair["label_b"]) == label_key(gb.label), "wrong witness labels")
        require(tuple(tuple(x) for x in pair["matching_stable_histogram"]) == histograms[a], "wrong witness histogram")
