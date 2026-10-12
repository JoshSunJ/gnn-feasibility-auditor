"""Optional small CPU GIN/GCN training experiments, after verified auditing."""

import math
import platform
import time

from .data import Dataset, dataset_object, label_key
from .report import audit
from .verify import verify_report


class BenchmarkError(ValueError):
    pass


def run_benchmarks(dataset: Dataset, *, models=("gin", "gcn"), seeds=(0, 1, 2),
                   epochs=300, hidden=32, layers=3, learning_rate=.01) -> dict:
    if not models or any(model not in ("gin", "gcn") for model in models):
        raise BenchmarkError("models must contain gin and/or gcn")
    if not seeds or any(type(seed) is not int or seed < 0 for seed in seeds):
        raise BenchmarkError("provide nonnegative integer seeds")
    if any(type(n) is not int or n <= 0 for n in (epochs, hidden, layers)):
        raise BenchmarkError("epochs, hidden size and layers must be positive integers")
    if not math.isfinite(learning_rate) or learning_rate <= 0:
        raise BenchmarkError("learning rate must be positive and finite")
    if any(len(g.node_ids) > 512 for g in dataset.graphs) or sum(len(g.node_ids) ** 2 for g in dataset.graphs) > 2_000_000:
        raise BenchmarkError("this small dense benchmark supports at most 512 nodes per graph and 2,000,000 total adjacency entries")
    try:
        import torch
        from torch import nn
    except ImportError as error:
        raise BenchmarkError("optional benchmarks need PyTorch; install with: python -m pip install '.[benchmark]'") from error

    # Every benchmark audits actual features and independently verifies the trace.
    proof = audit(dataset, include_certificate=True)
    verify_report(dataset, proof)
    dtype = torch.float32 if dataset.feature_dtype == "float32" else torch.float64
    label_keys = sorted(set(label_key(g.label) for g in dataset.graphs))
    targets = torch.tensor([label_keys.index(label_key(g.label)) for g in dataset.graphs], dtype=torch.long)
    tensors = []
    for graph in dataset.graphs:
        n = len(graph.node_ids)
        x = torch.tensor(graph.features, dtype=dtype).reshape(n, dataset.feature_dim)
        a = torch.zeros((n, n), dtype=dtype)
        for u, v in graph.edges:
            a[u, v] = a[v, u] = 1
        self_a = a + torch.eye(n, dtype=dtype)
        scale = self_a.sum(dim=1).rsqrt()
        normalized = scale[:, None] * self_a * scale[None, :]
        tensors.append((x, a, normalized))

    class MessagePassing(nn.Module):
        def __init__(self, kind):
            super().__init__()
            self.kind = kind
            self.input = nn.Linear(dataset.feature_dim, hidden)
            self.epsilon = nn.ParameterList([nn.Parameter(torch.zeros(())) for _ in range(layers)]) if kind == "gin" else None
            self.updates = nn.ModuleList([
                nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, hidden))
                if kind == "gin" else nn.Linear(hidden, hidden)
                for _ in range(layers)])
            self.head = nn.Linear(hidden * (layers + 1), len(label_keys))

        def forward(self):
            embeddings = []
            for x, adjacency, normalized in tensors:
                h = torch.relu(self.input(x))
                pools = [h.sum(dim=0)]
                for k, update in enumerate(self.updates):
                    messages = (1 + self.epsilon[k]) * h + adjacency @ h if self.kind == "gin" else normalized @ h
                    h = torch.relu(update(messages))
                    pools.append(h.sum(dim=0))
                embeddings.append(torch.cat(pools))
            return self.head(torch.stack(embeddings))

    old_threads = torch.get_num_threads()
    old_deterministic = torch.are_deterministic_algorithms_enabled()
    old_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    runs = []
    ceiling_correct = proof["training_accuracy_upper_bound"]["max_correct"]
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        # Preserve the caller's RNG state; these experiments use CPU only.
        with torch.random.fork_rng(devices=[]):
            for kind in models:
                for seed in seeds:
                    torch.manual_seed(seed)
                    model = MessagePassing(kind).to(dtype=dtype, device="cpu")
                    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
                    criterion = nn.CrossEntropyLoss()
                    start = time.perf_counter()
                    history, best_correct, best_epoch = [], -1, 0
                    observed_excess = False
                    for epoch in range(epochs + 1):
                        model.eval()
                        with torch.no_grad():
                            logits = model()
                            if not torch.isfinite(logits).all():
                                raise BenchmarkError(f"{kind} seed {seed}: nonfinite logits; try a smaller learning rate")
                            loss = float(criterion(logits, targets))
                            count = int((logits.argmax(dim=1) == targets).sum())
                        if count > best_correct:
                            best_correct, best_epoch = count, epoch
                        observed_excess |= count > ceiling_correct
                        if epoch % max(1, epochs // 40) == 0 or epoch == epochs:
                            history.append({"epoch": epoch, "training_loss": loss, "train_correct": count,
                                            "train_accuracy": count / len(dataset.graphs)})
                        if epoch == epochs:
                            break
                        model.train()
                        optimizer.zero_grad()
                        train_loss = criterion(model(), targets)
                        train_loss.backward()
                        optimizer.step()
                    indices = {g.id: i for i, g in enumerate(dataset.graphs)}
                    predictions = logits.argmax(dim=1).tolist()
                    max_delta, mismatched_classes, numerical_classes = 0., [], []
                    atol, rtol = (1e-6, 1e-5) if dtype == torch.float32 else (1e-10, 1e-9)
                    for item in proof["classes"]:
                        members = [indices[gid] for gid in item["graph_ids"]]
                        anchor = logits[members[0]]
                        delta = float((logits[members] - anchor).abs().max())
                        max_delta = max(delta, max_delta)
                        if len(set(predictions[i] for i in members)) > 1:
                            mismatched_classes.append(item["id"])
                        if not torch.allclose(logits[members], anchor.expand(len(members), -1), atol=atol, rtol=rtol):
                            numerical_classes.append(item["id"])
                    runs.append({
                        "model": kind.upper(), "seed": seed, "epochs": epochs,
                        "final_train_correct": count, "final_train_accuracy": count / len(dataset.graphs),
                        "final_training_loss": loss, "best_observed_train_correct": best_correct,
                        "best_observed_train_accuracy": best_correct / len(dataset.graphs), "best_observed_epoch": best_epoch,
                        "seconds": time.perf_counter() - start, "history": history,
                        "predictions": [{"graph_id": g.id, "actual_label": g.label, "predicted_label": label_keys[predictions[i]][1],
                                         "logits": logits[i].tolist()} for i, g in enumerate(dataset.graphs)],
                        "consistency": {"max_within_class_logit_difference": max_delta,
                                        "absolute_tolerance": atol, "relative_tolerance": rtol,
                                        "classes_exceeding_logit_tolerance": numerical_classes,
                                        "classes_with_different_predictions": mismatched_classes,
                                        "any_observed_accuracy_above_ceiling": observed_excess},
                    })
    finally:
        torch.set_num_threads(old_threads)
        torch.use_deterministic_algorithms(old_deterministic, warn_only=old_warn_only)
    return {
        "benchmark_version": 1, "split": "train", "core_certificate_verified": True,
        "audited_inputs": dataset_object(dataset),
        "training_accuracy_upper_bound": proof["training_accuracy_upper_bound"],
        "config": {"models": list(models), "seeds": list(seeds), "epochs": epochs, "hidden": hidden,
                   "layers": layers, "learning_rate": learning_rate, "feature_dtype": dataset.feature_dtype,
                   "device": "cpu", "optimizer": "Adam", "loss": "CrossEntropyLoss",
                   "readout": "concatenated per-layer sum pooling", "batching": "full training set",
                   "dropout": 0, "extra_node_features": False},
        "environment": {"python": platform.python_version(), "torch": torch.__version__, "platform": platform.platform()},
        "interpretation": "Measured training fits of small GIN/GCN implementations. Neither optimizer success nor this WL ceiling predicts test accuracy. Numerical consistency checks are diagnostics, not proofs.",
        "runs": runs,
    }
