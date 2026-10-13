import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest

from gnn_auditor.data import dataset_object, load_dataset, parse_dataset
from gnn_auditor.explorer import render_html
from gnn_auditor.explorer import render_verified_html
from gnn_auditor.partition import audit_partition
from gnn_auditor.verify import verify_report
from test_core import dataset, graph

ROOT = Path(__file__).resolve().parents[1]


class ExplorerTests(unittest.TestCase):
    def test_compact_export_keeps_full_exact_proof_in_download_and_final_only_view(self):
        data = parse_dataset(dataset(graph("a", 3, [(0, 1), (1, 2)], 2 ** 60), graph("b", 3, [(0, 1), (1, 2)], 2 ** 60 + 1)))
        report = audit_partition(data, include_certificate=True)
        html = render_verified_html(data, report)
        value = json.loads(re.search(r'<script id="audit-data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(value["inspection"]["mode"], "stable_only")
        self.assertNotIn("events", value["report"]["certificate"])
        verify_report(data, json.loads(value["report_json"]))
        self.assertEqual(json.loads(value["dataset_json"]), dataset_object(data))
        self.assertNotEqual(value["graph_label_text"]["a"], value["graph_label_text"]["b"])

    def test_export_embeds_verified_input_and_certificate(self):
        data = load_dataset(ROOT / "examples/conflicts.json")
        html = render_html(data)
        self.assertNotIn("__AUDIT_PAYLOAD__", html)
        value = json.loads(re.search(r'<script id="audit-data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(value["dataset"], dataset_object(data))
        verify_report(data, value["report"])

    def test_untrusted_strings_cannot_terminate_script(self):
        value = dataset(graph('</script><script>alert("x")</script>', 1, [], '<img src=x onerror=alert(1)>'))
        data = parse_dataset(value)
        html = render_html(data)
        embedded = re.search(r'<script id="audit-data" type="application/json">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn("<", embedded)
        self.assertEqual(json.loads(embedded)["dataset"], dataset_object(data))

    def test_wrong_benchmark_attachment_is_rejected(self):
        data = load_dataset(ROOT / "examples/conflicts.json")
        with self.assertRaisesRegex(ValueError, "actual inputs"):
            render_html(data, {"audited_inputs": {}, "training_accuracy_upper_bound": {}})

    def test_large_integer_labels_preserve_exact_display_and_exports(self):
        value = dataset(graph("a", 1, [], 2 ** 60), graph("b", 1, [], 2 ** 60 + 1))
        data = parse_dataset(value)
        html = render_html(data)
        embedded = json.loads(re.search(r'<script id="audit-data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertNotEqual(embedded["graph_label_text"]["a"], embedded["graph_label_text"]["b"])
        self.assertEqual(json.loads(embedded["dataset_json"]), dataset_object(data))
        verify_report(data, json.loads(embedded["report_json"]))


@unittest.skipUnless(importlib.util.find_spec("torch"), "optional PyTorch dependency is not installed")
class BenchmarkTests(unittest.TestCase):
    def test_trainable_models_obey_known_collision(self):
        from gnn_auditor.benchmark import run_benchmarks
        data = load_dataset(ROOT / "examples/conflicts.json")
        result = run_benchmarks(data, seeds=(17,), epochs=3, hidden=8, layers=2)
        self.assertTrue(result["core_certificate_verified"])
        self.assertEqual(len(result["runs"]), 2)
        for run in result["runs"]:
            c = run["consistency"]
            self.assertEqual(c["classes_with_different_predictions"], [])
            self.assertEqual(c["classes_exceeding_logit_tolerance"], [])
            self.assertFalse(c["any_observed_accuracy_above_ceiling"])
            self.assertLessEqual(run["best_observed_train_correct"], 4)
            self.assertNotEqual(run["history"][0]["training_loss"], run["history"][-1]["training_loss"])
        html = render_html(data, result)
        self.assertIn('"benchmark_version": 1', html)
        wrong = copy.deepcopy(result)
        wrong["audited_inputs"]["graphs"][0]["nodes"][0]["features"] = [2.]
        with self.assertRaises(ValueError):
            render_html(data, wrong)

    def test_reproducible_cpu_training_and_input_precision(self):
        from gnn_auditor.benchmark import run_benchmarks
        value = dataset(graph("a", 1, [], "a", [[1.]]), graph("b", 1, [], "b", [[1. + 2 ** -24]]), dtype="float32")
        data = parse_dataset(value)
        a = run_benchmarks(data, models=("gin",), seeds=(9,), epochs=2, hidden=4, layers=1)
        b = run_benchmarks(data, models=("gin",), seeds=(9,), epochs=2, hidden=4, layers=1)
        self.assertEqual(a["runs"][0]["predictions"], b["runs"][0]["predictions"])
        self.assertEqual(a["runs"][0]["history"], b["runs"][0]["history"])
        self.assertEqual(a["training_accuracy_upper_bound"]["fraction"], "1/2")
        self.assertEqual(a["runs"][0]["consistency"]["max_within_class_logit_difference"], 0.)

    def test_empty_graph_and_zero_dim_features(self):
        from gnn_auditor.benchmark import BenchmarkError, run_benchmarks
        data = parse_dataset(dataset(graph("empty", 0, [], "a"), graph("isolates", 2, [], "b", [[], []]), dim=0))
        result = run_benchmarks(data, models=("gcn",), seeds=(0,), epochs=1, hidden=4, layers=1)
        self.assertEqual(len(result["runs"][0]["predictions"]), 2)
        for kwargs in ({"epochs": 0}, {"learning_rate": float("nan")}, {"models": ("other",)}):
            with self.assertRaises(BenchmarkError):
                run_benchmarks(data, **kwargs)


if __name__ == "__main__":
    unittest.main()
