"""One isolated audit. Only verified, fully serialized artifacts are published."""

import json
from pathlib import Path
import sys

from ..data import InputError, dataset_object, loads_dataset
from ..explorer import render_verified_html
from ..inspection import inspection_payload
from ..partition import audit_partition
from ..refinement import refine
from ..report import build_report, certificate
from ..verify import verify_report
from .limits import BudgetExceeded, Limits, check_dataset


def run_audit(raw: str, directory: str, limits: Limits, connection):
    try:
        mode = "auto"
        if isinstance(raw, dict):
            mode, raw = raw["mode"], raw["raw"]
        if sys.platform.startswith("linux"):
            import resource
            # Hard OS limit supplements the parent's resident-memory watchdog.
            resource.setrlimit(resource.RLIMIT_AS, (limits.memory_mb * 1024**2,) * 2)
        dataset = loads_dataset(raw)
        del raw
        check_dataset(dataset, limits)
        nodes = sum(len(g.node_ids) for g in dataset.graphs)

        def progress(item):
            if nodes * (item.index + 1) > limits.max_trace_cells:
                raise BudgetExceeded("The refinement trace exceeded this service's budget. No ceiling was certified.")
            connection.send({"kind": "progress", "round": item.index, "color_count": len(item.palette)})

        selected = "partition" if mode == "partition" or (mode == "auto" and nodes > 512) else "trace"
        if selected == "partition":
            def step(item):
                if item["moved_vertices"] > limits.max_moved_vertices:
                    raise BudgetExceeded("The compact split evidence exceeded this service's budget. No ceiling was certified.")
                if item["processed_splitters"] % 25 == 0:
                    connection.send({"kind": "progress", "step": item["processed_splitters"], "color_count": item["color_count"]})
            report = audit_partition(dataset, max_pairs=100, include_certificate=True, on_step=step)
        else:
            result = refine(dataset, on_round=progress)
            report = build_report(dataset, result, max_pairs=100)
            report["certificate"] = certificate(dataset, result)
        verify_report(dataset, report)
        inputs = dataset_object(dataset)
        artifacts = {
            "report.json": lambda: json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",",":")),
            "inputs.json": lambda: json.dumps(inputs, ensure_ascii=False, allow_nan=False, separators=(",",":")),
            "view.json": lambda: json.dumps(inspection_payload(dataset, report, inputs=inputs), ensure_ascii=True, allow_nan=False, separators=(",",":")),
            "explorer.html": lambda: render_verified_html(dataset, report),
        }
        size = 0
        for filename, make in artifacts.items():
            contents = make()
            encoded = contents.encode("utf-8")
            size += len(encoded)
            if size > limits.max_output_bytes:
                raise BudgetExceeded("The verified report exceeds this service's output budget. Download a CLI report locally instead.")
            Path(directory, filename).write_bytes(encoded)
            del contents, encoded
        connection.send({"kind": "completed", "summary": {
            "graph_count": report["graph_count"], "node_count": report["node_count"],
            "class_count": report["class_count"],
            "training_accuracy_upper_bound": report["training_accuracy_upper_bound"],
            "unavoidable_training_errors": report["unavoidable_training_errors"],
            "conflicting_pair_count": report["conflicting_pair_count"],
            "certificate_verified": True,
            "engine": selected,
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
