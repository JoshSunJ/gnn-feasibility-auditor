import copy
from itertools import combinations, product
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from gnn_auditor.data import InputError, dataset_object, loads_dataset, parse_dataset
from gnn_auditor.refinement import _intern, refine
from gnn_auditor.report import audit, text_report
from gnn_auditor.verify import VerificationError, verify_report

ROOT = Path(__file__).resolve().parents[1]


def graph(gid, n, edges, label="a", features=None):
    return {"id": gid, "label": label,
            "nodes": [{"id": str(i), "features": [1.0] if features is None else features[i]} for i in range(n)],
            "edges": [[str(u), str(v)] for u, v in edges]}


def dataset(*graphs, dtype="float64", dim=1):
    return {"schema_version": 1, "split": "train", "graph_type": "simple_undirected",
            "feature_dtype": dtype, "feature_dim": dim, "graphs": list(graphs)}


def reference_pair(a, b):
    """Slow independent pairwise WL: linear equality search, expanded multisets,
    fixed safe number of rounds, no stability rule or production interner.
    """
    vectors = list(a.features) + list(b.features)
    palette = []
    colors = []
    for vector in vectors:
        if vector not in palette:
            palette.append(vector)
        colors.append(palette.index(vector))
    size = len(a.features)
    adjacency = list(a.adjacency) + [tuple(size + u for u in ns) for ns in b.adjacency]
    for _ in range(len(vectors) + 2):
        if sorted(colors[:size]) != sorted(colors[size:]):
            return False
        signatures = [(colors[v], tuple(sorted(colors[u] for u in ns))) for v, ns in enumerate(adjacency)]
        new_palette = []
        new_colors = []
        for signature in signatures:
            if signature not in new_palette:
                new_palette.append(signature)
            new_colors.append(new_palette.index(signature))
        colors = new_colors
    return True


class CoreTests(unittest.TestCase):
    def setUp(self):
        cycle = [(i, (i + 1) % 6) for i in range(6)]
        triangles = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)]
        self.demo = dataset(graph("cycle-6", 6, cycle, "connected"),
                            graph("cycle-6-copy", 6, cycle, "connected"),
                            graph("two-triangles", 6, triangles, "disconnected"),
                            graph("path-6", 6, [(i, i + 1) for i in range(5)], "connected"),
                            graph("marked-triangles", 6, triangles, "disconnected", [[2.0]] + [[1.0]] * 5))

    def test_demo_majority_and_witnesses(self):
        report = audit(parse_dataset(self.demo), include_certificate=True)
        self.assertEqual(report["training_accuracy_upper_bound"], {"max_correct": 4, "total": 5, "fraction": "4/5", "value": .8})
        self.assertEqual(report["class_count"], 3)
        self.assertEqual(report["indistinguishable_pair_count"], 3)
        self.assertEqual(report["conflicting_pair_count"], 2)
        self.assertEqual(report["unavoidable_training_errors"], 1)
        verify_report(parse_dataset(self.demo), json.loads(json.dumps(report)))
        self.assertIn("not a prediction of test accuracy", text_report(report))

    def test_round_zero_and_one_separation(self):
        graphs = [graph("one", 1, []), graph("two", 2, []),
                  graph("edge", 2, [(0, 1)]), graph("colored", 2, [], features=[[1], [2]])]
        rounds = refine(parse_dataset(dataset(*graphs))).rounds
        self.assertNotEqual(rounds[0].histograms[0], rounds[0].histograms[1])
        self.assertEqual(rounds[0].histograms[1], rounds[0].histograms[2])
        self.assertNotEqual(rounds[1].histograms[1], rounds[1].histograms[2])
        self.assertNotEqual(rounds[0].histograms[1], rounds[0].histograms[3])

    def test_separates_after_degree_round(self):
        a = graph("arms-311", 6, [(0, 1), (1, 2), (2, 3), (0, 4), (0, 5)])
        b = graph("arms-221", 6, [(0, 1), (1, 2), (0, 3), (3, 4), (0, 5)])
        result = refine(parse_dataset(dataset(a, b)))
        self.assertEqual(result.rounds[1].histograms[0], result.rounds[1].histograms[1])
        self.assertNotEqual(result.rounds[2].histograms[0], result.rounds[2].histograms[1])
        self.assertEqual(len(result.rounds[-1].palette), len(result.rounds[-2].palette))

    def test_permutation_and_ids_invariance(self):
        altered = copy.deepcopy(self.demo)
        rng = random.Random(84)
        rng.shuffle(altered["graphs"])
        for g in altered["graphs"]:
            mapping = {n["id"]: "renamed-" + str(rng.random()) for n in g["nodes"]}
            for n in g["nodes"]:
                n["id"] = mapping[n["id"]]
            g["edges"] = [[mapping[v], mapping[u]] for u, v in g["edges"]]
            rng.shuffle(g["nodes"])
            rng.shuffle(g["edges"])
        a, b = (audit(parse_dataset(x)) for x in (self.demo, altered))
        for key in ("classes", "training_accuracy_upper_bound", "conflicting_pair_count", "rounds"):
            self.assertEqual(a[key], b[key])

    def test_labels_do_not_enter_refinement(self):
        altered = copy.deepcopy(self.demo)
        for i, g in enumerate(altered["graphs"]):
            g["label"] = i
        self.assertEqual(refine(parse_dataset(self.demo)), refine(parse_dataset(altered)))

    def test_exact_feature_precision_and_signed_zero(self):
        a = graph("a", 1, [], features=[[1.0]])
        b = graph("b", 1, [], features=[[math.nextafter(1.0, 2.0)]])
        self.assertEqual(audit(parse_dataset(dataset(a, b)))["class_count"], 2)
        self.assertEqual(audit(parse_dataset(dataset(a, b, dtype="float32")))["class_count"], 1)
        a["nodes"][0]["features"] = [-0.0]
        b["nodes"][0]["features"] = [0]
        self.assertEqual(audit(parse_dataset(dataset(a, b)))["class_count"], 1)

    def test_neighbor_multiplicity_and_old_color(self):
        data = parse_dataset(dataset(graph("isolates", 3, []), graph("path", 3, [(0, 1), (1, 2)])))
        result = refine(data)
        self.assertEqual(len(result.rounds[0].palette), 1)
        self.assertEqual(len(result.rounds[1].palette), 3)
        for previous, current in zip(result.rounds, result.rounds[1:]):
            owner = {}
            for old, new in zip(sum(previous.node_colors, ()), sum(current.node_colors, ())):
                self.assertEqual(owner.setdefault(new, old), old)

    def test_forced_hash_collisions(self):
        class CollidingTuple(tuple):
            def __hash__(self):
                return 42
        a, b = CollidingTuple((1, (2, 2))), CollidingTuple((1, (2, 3)))
        colors, palette = _intern([a, b, a])
        self.assertEqual(len(palette), 2)
        self.assertEqual(colors[0], colors[2])
        self.assertNotEqual(colors[0], colors[1])

    def test_all_small_simple_graphs_against_pairwise_oracle(self):
        graphs = []
        for n in range(5):
            possible = list(combinations(range(n), 2))
            for mask in range(1 << len(possible)):
                graphs.append(graph(f"n{n}-{mask}", n, [e for i, e in enumerate(possible) if mask & (1 << i)]))
        data = parse_dataset(dataset(*graphs))
        final = refine(data).stable_histograms
        self.assertEqual(len(data.graphs), 76)
        for i, j in combinations(range(len(data.graphs)), 2):
            self.assertEqual(final[i] == final[j], reference_pair(data.graphs[i], data.graphs[j]), (i, j))

    def test_seeded_feature_labeled_oracle(self):
        rng = random.Random(20261010)
        graphs = []
        for i in range(60):
            n = rng.randrange(0, 9)
            edges = [e for e in combinations(range(n), 2) if rng.random() < .3]
            features = [[rng.choice([0., 1., 2.])] for _ in range(n)]
            graphs.append(graph(str(i), n, edges, features=features))
        # Add deliberately repeated attributed structures with independent IDs.
        for i in range(10):
            duplicate = copy.deepcopy(graphs[i])
            duplicate["id"] = "copy-" + str(i)
            graphs.append(duplicate)
        data = parse_dataset(dataset(*graphs))
        final = refine(data).stable_histograms
        for i, j in combinations(range(len(data.graphs)), 2):
            self.assertEqual(final[i] == final[j], reference_pair(data.graphs[i], data.graphs[j]), (i, j))

    def test_empty_graphs_zero_dim_and_typed_labels(self):
        data = parse_dataset(dataset(graph("a", 0, [], 1), graph("b", 0, [], "1"),
                                     graph("c", 2, [], "1", [[], []]), dim=0))
        report = audit(data, include_certificate=True)
        self.assertEqual(report["training_accuracy_upper_bound"]["fraction"], "2/3")
        self.assertEqual(len(report["classes"][0]["majority_labels"]), 2)
        verify_report(data, json.loads(json.dumps(report)))

    def test_majority_bound_against_brute_force_class_predictions(self):
        data = parse_dataset(dataset(*(graph(str(i), 1 if i < 5 else 2, [], label)
                                       for i, label in enumerate(["a", "b", "b", "c", "c", "a", "b", "b"]))))
        result = refine(data)
        histograms = list(dict.fromkeys(result.stable_histograms))
        best = 0
        for predictions in product(["a", "b", "c"], repeat=len(histograms)):
            score = sum(g.label == predictions[histograms.index(h)] for g, h in zip(data.graphs, result.stable_histograms))
            best = max(best, score)
        self.assertEqual(best, audit(data)["training_accuracy_upper_bound"]["max_correct"])

    def test_bounded_pair_output_counts(self):
        data = parse_dataset(self.demo)
        for cap in [0, 1, 20]:
            report = audit(data, max_pairs=cap, include_certificate=True)
            self.assertEqual(report["conflict_witnesses_shown"], min(cap, 2))
            self.assertEqual(report["conflict_witnesses_omitted"], 2 - min(cap, 2))
            verify_report(data, json.loads(json.dumps(report)))

    def test_certificate_detects_tampering_and_early_stop(self):
        data = parse_dataset(self.demo)
        report = json.loads(json.dumps(audit(data, include_certificate=True)))
        mutations = [lambda r: r["certificate"]["rounds"][1]["node_colors"][0].__setitem__(0, 999),
                     lambda r: r["training_accuracy_upper_bound"].__setitem__("max_correct", 5),
                     lambda r: r["classes"][0]["graph_ids"].append("path-6"),
                     lambda r: r["certificate"]["rounds"].pop(),
                     lambda r: r["certificate"]["rounds"][0]["palette"][0].__setitem__(0, "0x1.8000000000000p+0"),
                     lambda r: r["conflict_witnesses"][0].__setitem__("label_b", "connected")]
        for mutate in mutations:
            bad = copy.deepcopy(report)
            mutate(bad)
            with self.assertRaises(VerificationError):
                verify_report(data, bad)

    def test_certificate_palette_remapping_is_valid(self):
        data = parse_dataset(self.demo)
        report = json.loads(json.dumps(audit(data, include_certificate=True)))
        # Initial colors can be any injective assignment. Relabel all rounds,
        # updating old-color references, neighbor multiplicities and histograms.
        previous_mapping = None
        for item in report["certificate"]["rounds"]:
            palette = item["palette"]
            mapping = {i: len(palette) - 1 - i for i in range(len(palette))}
            if previous_mapping is not None:
                palette = [[previous_mapping[old], sorted([[previous_mapping[c], n] for c, n in neighbors])]
                           for old, neighbors in palette]
            item["palette"] = list(reversed(palette))
            item["node_colors"] = [[mapping[c] for c in colors] for colors in item["node_colors"]]
            item["histograms"] = [sorted([[mapping[c], n] for c, n in hist]) for hist in item["histograms"]]
            if item["round"] == report["stabilization_round"]:
                for group in report["classes"]:
                    group["stable_histogram"] = sorted([[mapping[c], n] for c, n in group["stable_histogram"]])
            for pair in report["conflict_witnesses"]:
                t = item["round"]
                pair["matching_histograms_by_round"][t] = sorted([[mapping[c], n] for c, n in pair["matching_histograms_by_round"][t]])
            previous_mapping = mapping
        verify_report(data, report)

    def test_input_rejection(self):
        mutations = [lambda d: d.__setitem__("split", "test"),
                     lambda d: d.__setitem__("graph_type", "directed"),
                     lambda d: d.__setitem__("directed", True),
                     lambda d: d.__setitem__("graphs", []),
                     lambda d: d.__setitem__("schema_version", True),
                     lambda d: d.__setitem__("feature_dim", -1),
                     lambda d: d["graphs"][0].__setitem__("graph_features", [3]),
                     lambda d: d["graphs"][0].__setitem__("label", True),
                     lambda d: d["graphs"][0]["nodes"][0].pop("features"),
                     lambda d: d["graphs"][0]["nodes"][0].__setitem__("features", [1, 2]),
                     lambda d: d["graphs"][0]["nodes"][0].__setitem__("features", [True]),
                     lambda d: d["graphs"][0]["nodes"][0].__setitem__("features", [float("nan")]),
                     lambda d: d["graphs"][0]["nodes"][0].__setitem__("features", [float("inf")]),
                     lambda d: d["graphs"][0]["nodes"][0].__setitem__("features", [10 ** 400]),
                     lambda d: d["graphs"][0]["nodes"][1].__setitem__("id", "0"),
                     lambda d: d["graphs"][1].__setitem__("id", "cycle-6"),
                     lambda d: d["graphs"][0]["edges"].append(["0", "0"]),
                     lambda d: d["graphs"][0]["edges"].append(["unknown", "0"]),
                     lambda d: d["graphs"][0]["edges"].append(["1", "0"]),
                     lambda d: d["graphs"][0]["edges"].append(["0", "3", 2])]
        for mutate in mutations:
            invalid = copy.deepcopy(self.demo)
            mutate(invalid)
            with self.assertRaises(InputError):
                parse_dataset(invalid)
        overflow = copy.deepcopy(self.demo)
        overflow["feature_dtype"] = "float32"
        overflow["graphs"][0]["nodes"][0]["features"] = [1e100]
        with self.assertRaises(InputError):
            parse_dataset(overflow)
        for text in ['{"split":"train","split":"test"}', '{"value":NaN}', '{', '{"value":' + '1' * 5000 + '}', json.dumps(self.demo).replace('1.0', '1e999', 1)]:
            with self.assertRaises(InputError):
                loads_dataset(text)

    def test_representation_round_trip(self):
        data = parse_dataset(self.demo)
        self.assertEqual(loads_dataset(json.dumps(dataset_object(data))), data)

    def test_cli_audit_verify_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            output = Path(directory) / "report.json"
            path.write_text(json.dumps(self.demo))
            args = [sys.executable, "-m", "gnn_auditor"]
            run = subprocess.run(args + ["audit", str(path), "--format", "json", "--certificate", "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(output.read_text())["training_accuracy_upper_bound"]["fraction"], "4/5")
            check = subprocess.run(args + ["verify", str(path), str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            path.write_text("{}")
            bad = subprocess.run(args + ["audit", str(path)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
