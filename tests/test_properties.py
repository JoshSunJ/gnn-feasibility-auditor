"""Generated checks complement the independent small-graph oracle."""

import importlib.util
import unittest

if importlib.util.find_spec("hypothesis"):
    from hypothesis import given, settings, strategies as st
    from gnn_auditor.data import parse_dataset
    from gnn_auditor.report import audit
    from gnn_auditor.refinement import refine

    class PropertyTests(unittest.TestCase):
        @settings(max_examples=60, deadline=None, derandomize=True)
        @given(st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=10), st.integers(min_value=0, max_value=1023))
        def test_renaming_order_and_labels_do_not_change_structural_partition(self, features, mask):
            n = len(features)
            edges = [[str(i), str(i+1)] for i in range(n-1) if mask & (1 << i)]
            graph = {"id": "a", "label": "first", "nodes": [{"id": str(i), "features": [x]} for i, x in enumerate(features)], "edges": edges}
            other = {"id": "b", "label": "second", "nodes": [{"id": "v" + str(i), "features": [features[i]]} for i in reversed(range(n))], "edges": [["v" + v, "v" + u] for u, v in reversed(edges)]}
            data = parse_dataset({"schema_version": 1, "split": "train", "graph_type": "simple_undirected", "feature_dtype": "float32", "feature_dim": 1, "graphs": [graph, other]})
            result = refine(data)
            self.assertEqual(result.stable_histograms[0], result.stable_histograms[1])
            report = audit(data)
            self.assertEqual(report["training_accuracy_upper_bound"]["fraction"], "1/2")
