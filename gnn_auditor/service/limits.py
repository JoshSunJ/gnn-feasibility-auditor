"""Explicit service budgets. Exceeding a budget is an incomplete audit."""

from dataclasses import asdict, dataclass
import os

from ..data import Dataset


class BudgetExceeded(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    max_bytes: int = 1_048_576
    max_graphs: int = 128
    max_nodes: int = 2048
    max_edges: int = 8192
    max_feature_dim: int = 64
    max_trace_cells: int = 131_072
    max_output_bytes: int = 16_777_216
    timeout_seconds: float = 20
    memory_mb: int = 256
    max_active: int = 1
    max_queued: int = 3
    max_retained: int = 8
    ttl_seconds: float = 900

    def __post_init__(self):
        if any(value <= 0 for value in asdict(self).values()):
            raise ValueError("all service limits must be positive")
        if self.max_retained < self.max_active + self.max_queued:
            raise ValueError("retained capacity must cover admitted jobs")

    @classmethod
    def from_env(cls):
        values = {}
        for key, value in asdict(cls()).items():
            raw = os.getenv("AUDITOR_" + key.upper())
            if raw is not None:
                values[key] = float(raw) if isinstance(value, float) or key in {"timeout_seconds", "ttl_seconds"} else int(raw)
        return cls(**values)

    def public(self):
        return asdict(self)


def check_dataset(dataset: Dataset, limits: Limits):
    checks = {
        "graphs": (len(dataset.graphs), limits.max_graphs),
        "nodes": (sum(len(g.node_ids) for g in dataset.graphs), limits.max_nodes),
        "edges": (sum(len(g.edges) for g in dataset.graphs), limits.max_edges),
        "feature dimension": (dataset.feature_dim, limits.max_feature_dim),
    }
    for name, (actual, maximum) in checks.items():
        if actual > maximum:
            raise BudgetExceeded(f"Too many {name}: {actual}; this service accepts at most {maximum}.")
