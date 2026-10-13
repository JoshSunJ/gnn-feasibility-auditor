"""A self-contained local interface for exploring a verified audit."""

import json
from pathlib import Path

from .data import Dataset, dataset_object
from .report import audit
from .verify import verify_report
from .inspection import inspection_payload


def render_html(dataset: Dataset, benchmark: dict | None = None) -> str:
    report = audit(dataset, max_pairs=100, include_certificate=True)
    return render_verified_html(dataset, report, benchmark)


def render_verified_html(dataset: Dataset, report: dict, benchmark: dict | None = None) -> str:
    """Render supplied evidence only after independent replay against actual inputs."""
    verify_report(dataset, report)
    if benchmark is not None:
        # A benchmark is an empirical attachment, not certificate evidence.
        if benchmark.get("audited_inputs") != dataset_object(dataset):
            raise ValueError("benchmark actual inputs do not match this dataset")
        if benchmark.get("training_accuracy_upper_bound") != report["training_accuracy_upper_bound"]:
            raise ValueError("benchmark training ceiling does not match this dataset")
        ids = {g.id for g in dataset.graphs}
        for run in benchmark.get("runs", []):
            if {p["graph_id"] for p in run["predictions"]} != ids:
                raise ValueError("benchmark graph IDs do not match this dataset")
            actual = {g.id: (type(g.label), g.label) for g in dataset.graphs}
            if any((type(p["actual_label"]), p["actual_label"]) != actual[p["graph_id"]] for p in run["predictions"]):
                raise ValueError("benchmark labels do not match this dataset")
    inputs = dataset_object(dataset)
    # JS numbers cannot preserve arbitrarily large integer labels. Use exact
    # source text for downloads and parallel textual labels for all display.
    payload = {**inspection_payload(dataset, report, inputs=inputs), "benchmark": benchmark,
               "dataset_json": json.dumps(inputs, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n",
               "report_json": json.dumps(report, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"}
    safe_json = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = Path(__file__).with_name("explorer.html").read_text(encoding="utf-8")
    return template.replace("__AUDIT_PAYLOAD__", safe_json)
