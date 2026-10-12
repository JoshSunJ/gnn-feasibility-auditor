"""Strict ingestion: preserve all supported model inputs, reject everything else."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import struct
from typing import Any


class InputError(ValueError):
    """The input is outside the declared audit contract."""


@dataclass(frozen=True)
class Graph:
    id: str
    label: str | int
    node_ids: tuple[str, ...]
    features: tuple[tuple[float, ...], ...]
    edges: tuple[tuple[int, int], ...]
    adjacency: tuple[tuple[int, ...], ...]
    description: str = ""


@dataclass(frozen=True)
class Dataset:
    graphs: tuple[Graph, ...]
    feature_dtype: str
    feature_dim: int
    description: str = ""


def feature_key(vector: tuple[float, ...]) -> tuple[str, ...]:
    # Hexadecimal representations encode exact represented values, never proximity.
    return tuple((0.0 if x == 0 else x).hex() for x in vector)


def label_key(label: str | int) -> tuple[str, str | int]:
    return ("integer" if type(label) is int else "string", label)


def _fail(where: str, message: str) -> None:
    raise InputError(f"{where}: {message}")


def _object(value: Any, required: set[str], optional: set[str], where: str) -> dict:
    if not isinstance(value, dict):
        _fail(where, "expected an object")
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing:
        _fail(where, f"missing keys: {', '.join(sorted(missing))}")
    if extra:
        _fail(where, f"unsupported keys: {', '.join(sorted(extra))}")
    if "description" in value and not isinstance(value["description"], str):
        _fail(where, "description must be a string")
    return value


def _list(value: Any, where: str) -> list:
    if not isinstance(value, list):
        _fail(where, "expected an array")
    return value


def _id(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(where, "expected a nonempty string identifier")
    return value


def _number(value: Any, dtype: str, where: str) -> float:
    if type(value) not in (int, float):
        _fail(where, "features must be numeric (booleans are invalid)")
    try:
        result = float(value)
        if dtype == "float32":
            result = struct.unpack("!f", struct.pack("!f", result))[0]
    except (ValueError, OverflowError, struct.error):
        _fail(where, f"feature overflows {dtype}")
    if not math.isfinite(result):
        _fail(where, "features must be finite")
    return 0.0 if result == 0 else result


def parse_dataset(value: Any) -> Dataset:
    """Validate JSON-shaped data, convert once to the declared model precision."""
    root = _object(value, {"schema_version", "split", "graph_type", "feature_dtype", "feature_dim", "graphs"}, {"description"}, "dataset")
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        _fail("dataset", "schema_version must be integer 1")
    if root["split"] != "train":
        _fail("dataset", "split must be 'train'; supply only training samples")
    if root["graph_type"] != "simple_undirected":
        _fail("dataset", "only simple_undirected graphs are supported")
    dtype = root["feature_dtype"]
    if dtype not in ("float32", "float64"):
        _fail("dataset", "feature_dtype must be float32 or float64")
    dim = root["feature_dim"]
    if type(dim) is not int or dim < 0:
        _fail("dataset", "feature_dim must be a nonnegative integer")
    items = _list(root["graphs"], "dataset.graphs")
    if not items:
        _fail("dataset", "empty training dataset has undefined accuracy")
    graphs = []
    seen_graphs = set()
    for i, item in enumerate(items):
        where = f"graphs[{i}]"
        item = _object(item, {"id", "label", "nodes", "edges"}, {"description"}, where)
        gid = _id(item["id"], where + ".id")
        if gid in seen_graphs:
            _fail(where, f"duplicate graph ID {gid!r}")
        seen_graphs.add(gid)
        label = item["label"]
        if type(label) not in (int, str):
            _fail(where, "label must be an integer or string")
        node_ids, features, indices = [], [], {}
        for j, node in enumerate(_list(item["nodes"], where + ".nodes")):
            nw = f"{where}.nodes[{j}]"
            node = _object(node, {"id", "features"}, set(), nw)
            nid = _id(node["id"], nw + ".id")
            if nid in indices:
                _fail(nw, f"duplicate node ID {nid!r}")
            vector = _list(node["features"], nw + ".features")
            if len(vector) != dim:
                _fail(nw, f"expected {dim} feature values, got {len(vector)}")
            indices[nid] = j
            node_ids.append(nid)
            features.append(tuple(_number(x, dtype, nw + f".features[{k}]") for k, x in enumerate(vector)))
        edge_set = set()
        adjacency = [set() for _ in node_ids]
        for j, edge in enumerate(_list(item["edges"], where + ".edges")):
            ew = f"{where}.edges[{j}]"
            edge = _list(edge, ew)
            if len(edge) != 2:
                _fail(ew, "expected two endpoints; edge attributes are unsupported")
            u, v = (_id(x, ew) for x in edge)
            if u not in indices or v not in indices:
                _fail(ew, "endpoint refers to an undeclared node")
            if u == v:
                _fail(ew, "self-loops are unsupported")
            a, b = sorted((indices[u], indices[v]))
            if (a, b) in edge_set:
                _fail(ew, "duplicate unordered edge; parallel edges are unsupported")
            edge_set.add((a, b))
            adjacency[a].add(b)
            adjacency[b].add(a)
        graphs.append(Graph(gid, label, tuple(node_ids), tuple(features), tuple(sorted(edge_set)), tuple(tuple(sorted(neighbors)) for neighbors in adjacency), item.get("description", "")))
    return Dataset(tuple(graphs), dtype, dim, root.get("description", ""))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def loads_dataset(text: str) -> Dataset:
    try:
        value = json.loads(text, object_pairs_hook=_unique_object,
                           parse_constant=lambda x: _fail("JSON", f"nonfinite value {x}"))
    except InputError:
        raise
    except (ValueError, RecursionError) as error:
        raise InputError(f"invalid JSON: {error}") from error
    return parse_dataset(value)


def load_dataset(path: str | Path) -> Dataset:
    try:
        return loads_dataset(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        raise InputError(f"cannot read dataset: {error}") from error


def dataset_object(dataset: Dataset) -> dict:
    """Export the represented inputs, including isolated and empty graphs."""
    return {
        "schema_version": 1, "split": "train", "graph_type": "simple_undirected",
        "feature_dtype": dataset.feature_dtype, "feature_dim": dataset.feature_dim,
        "description": dataset.description,
        "graphs": [{"id": g.id, "label": g.label, "description": g.description,
                    "nodes": [{"id": n, "features": list(x)} for n, x in zip(g.node_ids, g.features)],
                    "edges": [[g.node_ids[u], g.node_ids[v]] for u, v in g.edges]}
                   for g in dataset.graphs],
    }
