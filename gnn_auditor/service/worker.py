"""One isolated audit. Only verified, fully serialized artifacts are published."""

import json
from pathlib import Path
import sys

from ..data import InputError, dataset_object, loads_dataset
from ..explorer import render_verified_html
from ..refinement import refine
from ..report import build_report, certificate
from ..verify import verify_report
from .limits import BudgetExceeded, Limits, check_dataset


def run_audit(raw: str, directory: str, limits: Limits, connection):
    try:
        if sys.platform.startswith("linux"):
            import resource
            # Hard OS limit supplements the parent's resident-memory watchdog.
            resource.setrlimit(resource.RLIMIT_AS, (limits.memory_mb * 1024**2,) * 2)
        dataset = loads_dataset(raw)
        check_dataset(dataset, limits)
        nodes = sum(len(g.node_ids) for g in dataset.graphs)

        def progress(item):
            if nodes * (item.index + 1) > limits.max_trace_cells:
                raise BudgetExceeded("The refinement trace exceeded this service's budget. No ceiling was certified.")
            connection.send({"kind": "progress", "round": item.index, "color_count": len(item.palette)})

        result = refine(dataset, on_round=progress)
        report = build_report(dataset, result, max_pairs=100)
        report["certificate"] = certificate(dataset, result)
        verify_report(dataset, report)
        artifacts = {
            "report": ("report.json", json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2)),
            "inputs": ("inputs.json", json.dumps(dataset_object(dataset), ensure_ascii=False, allow_nan=False, indent=2)),
            "explorer": ("explorer.html", render_verified_html(dataset, report)),
            "view": ("view.json", json.dumps({"dataset": dataset_object(dataset), "report": report,
                "graph_label_text": {g.id: json.dumps(g.label, ensure_ascii=True) for g in dataset.graphs},
                "class_label_text": {c["id"]: [json.dumps(x["label"], ensure_ascii=True) for x in c["label_counts"]] for c in report["classes"]}}, ensure_ascii=True, allow_nan=False)),
        }
        size = 0
        for filename, contents in artifacts.values():
            encoded = contents.encode("utf-8")
            size += len(encoded)
            if size > limits.max_output_bytes:
                raise BudgetExceeded("The verified report exceeds this service's output budget. Download a CLI report locally instead.")
            Path(directory, filename).write_bytes(encoded)
        connection.send({"kind": "completed", "summary": {
            "graph_count": report["graph_count"], "node_count": report["node_count"],
            "class_count": report["class_count"],
            "training_accuracy_upper_bound": report["training_accuracy_upper_bound"],
            "unavoidable_training_errors": report["unavoidable_training_errors"],
            "conflicting_pair_count": report["conflicting_pair_count"],
            "certificate_verified": True,
        }})
    except InputError as error:
        connection.send({"kind": "rejected", "code": "invalid_input", "message": str(error)})
    except (BudgetExceeded, MemoryError) as error:
        connection.send({"kind": "rejected", "code": "resource_limit", "message": str(error) or "Audit memory budget exceeded; no certified ceiling."})
    except Exception:
        # Do not log uploaded contents or leak internals through the response.
        connection.send({"kind": "failed", "code": "audit_failed", "message": "The audit failed. No ceiling was certified. Try the CLI or a smaller supported input."})
    finally:
        connection.close()
