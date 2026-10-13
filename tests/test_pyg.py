import importlib.util
import unittest

AVAILABLE = bool(importlib.util.find_spec("torch") and importlib.util.find_spec("torch_geometric"))
if AVAILABLE:
    import torch
    from torch_geometric.data import Data
    from gnn_auditor.data import InputError, dataset_object
    from gnn_auditor.pyg import audit_pyg, dataset_from_pyg
    from gnn_auditor.verify import verify_report


@unittest.skipUnless(AVAILABLE, "optional PyG adapter dependencies are not installed")
class PyGTests(unittest.TestCase):
    def graph(self, dtype=None):
        return Data(x=torch.tensor([[1],[2],[3]],dtype=dtype or torch.float64), edge_index=torch.tensor([[0,1],[1,0]]), y=torch.tensor([7]), num_nodes=3)

    def test_preserves_actual_features_precision_isolates_and_selected_samples(self):
        graph=self.graph(torch.float32)
        data=dataset_from_pyg([self.graph(),graph],train_indices=[1])
        exported=dataset_object(data)
        self.assertEqual(exported["feature_dtype"],"float32")
        self.assertEqual(exported["graphs"][0]["id"],"sample-1")
        self.assertEqual(data.graphs[0].features,((1.,),(2.,),(3.,)))
        self.assertEqual(data.graphs[0].adjacency[2],())
        self.assertEqual(data.graphs[0].edges,((0,1),))
        report=audit_pyg([self.graph(),graph],train_indices=[1],include_certificate=True)
        verify_report(data,report)

    def test_rejects_missing_extra_and_nonreciprocal_or_parallel_inputs(self):
        graphs=[]
        graph=self.graph();graph.x=None;graphs.append(graph)
        graph=self.graph();graph.edge_attr=torch.ones(2,1);graphs.append(graph)
        graph=self.graph();graph.pos=torch.ones(3,2);graphs.append(graph)
        graph=self.graph();graph.edge_index=torch.tensor([[0],[1]]);graphs.append(graph)
        graph=self.graph();graph.edge_index=torch.tensor([[0,1,0,1],[1,0,1,0]]);graphs.append(graph)
        graph=self.graph();graph.num_nodes=2;graphs.append(graph)
        graph=self.graph();graph.y=torch.tensor([1,2]);graphs.append(graph)
        for graph in graphs:
            with self.subTest(graph=graph),self.assertRaises(InputError):dataset_from_pyg([graph],train_indices=[0])

    def test_training_selection_and_precision_contract(self):
        for indices in ([],[0,0],[-1],[2],[True]):
            with self.assertRaises(InputError):dataset_from_pyg([self.graph()],train_indices=indices)
        with self.assertRaises(InputError):dataset_from_pyg([self.graph(torch.float32),self.graph(torch.float64)],train_indices=[0,1])

    def test_empty_graph_and_feature_preserving_permutation(self):
        empty=Data(x=torch.empty(0,1,dtype=torch.float64),edge_index=torch.empty(2,0,dtype=torch.long),y=torch.tensor(4),num_nodes=0)
        self.assertEqual(audit_pyg([empty],train_indices=[0])["graph_count"],1)
        first=self.graph(); second=self.graph(); second.x=first.x[[2,1,0]];second.edge_index=torch.tensor([[2,1],[1,2]]);second.y=torch.tensor(8)
        report=audit_pyg([first,second],train_indices=[0,1])
        self.assertEqual(report["training_accuracy_upper_bound"]["fraction"],"1/2")
