"""Optional adapter for in-memory PyG Data objects; never loads pickle files."""

from collections import Counter

from .data import InputError, parse_dataset
from .report import audit


def dataset_from_pyg(graphs, *, train_indices):
    """Preserve the declared training tensors; reject unsupported model inputs.

    Only x, edge_index, y and num_nodes are accepted. Reciprocal COO entries
    represent one simple undirected edge. Duplicate directed entries are invalid.
    Call this after the actual model preprocessing; no features are synthesized.
    """
    try:
        import torch
        from torch_geometric.data import Data
    except ImportError as error:
        raise InputError("The optional PyG adapter needs torch and torch-geometric.") from error
    indices = list(train_indices)
    if not indices or any(type(i) is not int or i < 0 or i >= len(graphs) for i in indices) or len(set(indices)) != len(indices):
        raise InputError("train_indices must be a nonempty, unique list of valid integer sample positions")
    exported = []
    contract = None
    integer_types = (torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64)
    for i in indices:
        graph = graphs[i]
        if not isinstance(graph, Data):
            raise InputError(f"sample {i}: expected a PyG Data object")
        extra = set(graph.keys()) - {"x", "edge_index", "y", "num_nodes"}
        if extra:
            raise InputError(f"sample {i}: unsupported model fields: {', '.join(sorted(extra))}")
        x = graph.x
        if not isinstance(x, torch.Tensor) or x.ndim != 2 or x.dtype not in (torch.float32, torch.float64):
            raise InputError(f"sample {i}: x must be an explicit two-dimensional float32/float64 tensor")
        if x.layout != torch.strided:
            raise InputError(f"sample {i}: sparse feature tensors are unsupported")
        n, dim = x.shape
        if graph.num_nodes != n:
            raise InputError(f"sample {i}: num_nodes does not match x, including isolated nodes")
        current = ("float32" if x.dtype == torch.float32 else "float64", dim)
        if contract is not None and current != contract:
            raise InputError("all training samples must have the same feature dimension and precision")
        contract = current
        y = graph.y
        if not isinstance(y, torch.Tensor) or y.numel() != 1 or y.dtype not in integer_types:
            raise InputError(f"sample {i}: y must contain one integer graph-class label")
        edges = graph.edge_index
        if not isinstance(edges, torch.Tensor) or edges.ndim != 2 or edges.shape[0] != 2 or edges.dtype not in (torch.int32, torch.int64):
            raise InputError(f"sample {i}: edge_index must be an integer tensor of shape [2, E]")
        if edges.layout != torch.strided:
            raise InputError(f"sample {i}: sparse edge_index is unsupported")
        counts = Counter(tuple(edge) for edge in edges.detach().cpu().t().tolist())
        for (u,v), count in counts.items():
            if u == v or not (0 <= u < n and 0 <= v < n):
                raise InputError(f"sample {i}: self-loop or invalid endpoint")
            if count != 1 or counts[(v,u)] != 1:
                raise InputError(f"sample {i}: require exactly one COO entry in each direction per simple undirected edge")
        exported.append({"id": f"sample-{i}", "label": int(y.item()),
                         "nodes": [{"id": str(v), "features": features} for v, features in enumerate(x.detach().cpu().tolist())],
                         "edges": [[str(u), str(v)] for u,v in sorted(counts) if u < v]})
    dtype, dim = contract
    return parse_dataset({"schema_version": 1, "split": "train", "graph_type": "simple_undirected",
                          "feature_dtype": dtype, "feature_dim": dim, "graphs": exported})


def audit_pyg(graphs, *, train_indices, max_pairs=20, include_certificate=False):
    return audit(dataset_from_pyg(graphs, train_indices=train_indices), max_pairs, include_certificate)
