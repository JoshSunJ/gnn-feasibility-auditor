"""Normalize verified report inspection, keeping summary steps distinct from rounds."""

from collections import Counter
import json

from .data import dataset_object


def inspection_payload(dataset, report, *, inputs=None):
    inputs = dataset_object(dataset) if inputs is None else inputs
    summary = report["report_version"] == 2
    if summary:
        colors = report["certificate"]["final_node_colors"]
        palette = [None] * report["final_color_count"]
        histograms = []
        for graph, row in zip(dataset.graphs, colors):
            histograms.append(tuple(sorted(Counter(row).items())))
            for v, color in enumerate(row):
                if palette[color] is None:
                    palette[color] = (color, tuple(sorted(Counter(row[u] for u in graph.adjacency[v]).items())))
        rounds = [{"round": 0, "palette": palette, "node_colors": colors, "histograms": histograms}]
    else:
        rounds = None
    inspection = {"mode": "stable_only" if summary else "rounds"}
    if rounds is not None:
        inspection["rounds"] = rounds
    # Split events are exported in the certificate, but the inspector only
    # needs final colors. Avoid a second large copy in every viewer download.
    displayed_report = {**report, "certificate": {"version": 2}} if summary else report
    return {"dataset": inputs, "report": displayed_report, "inspection": inspection,
            "graph_label_text": {g.id: json.dumps(g.label, ensure_ascii=True) for g in dataset.graphs},
            "class_label_text": {c["id"]: [json.dumps(x["label"], ensure_ascii=True) for x in c["label_counts"]] for c in report["classes"]}}
