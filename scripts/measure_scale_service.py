"""Measure isolated service jobs, including real inputs regenerated separately.

No PyTorch import: serving-worker RSS is separate from dataset loading memory.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gnn_auditor.service.jobs import JobManager
from gnn_auditor.service.limits import Limits
from measure_service import case


def measure(raw, repetitions, mode="auto"):
    observations = []
    for _ in range(repetitions):
        manager = JobManager(Limits())
        try:
            started = time.monotonic()
            job = manager.submit(raw, mode)
            while job["status"] in {"queued", "running"}:
                time.sleep(.01)
                job = manager.get(job["id"])
            artifacts = {}
            if job["status"] == "completed":
                for name in ("inputs", "report", "view", "explorer"):
                    with manager.open_artifact(job["id"], name) as stream:
                        artifacts[name] = sum(len(chunk) for chunk in iter(lambda: stream.read(65_536), b""))
            observations.append({"status": job["status"], "wall_seconds": time.monotonic() - started,
                                 "worker_seconds": job["runtime_seconds"], "sampled_peak_mb": job["peak_memory_mb"],
                                 "summary": job["summary"], "error": job["error"], "artifact_bytes": artifacts})
        finally:
            manager.close()
    return {"input_bytes": len(raw.encode("utf-8")), "mode": mode, "observations": observations,
            "median_seconds": statistics.median(item["wall_seconds"] for item in observations),
            "max_seconds": max(item["wall_seconds"] for item in observations),
            "maximum_sampled_peak_mb": max(item["sampled_peak_mb"] for item in observations)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, help="root used by real_data_study.py")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("docs/scale-service-performance.json"))
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    rows = []
    for nodes, topology, mode in [(512, "path", "partition"), (6000, "path", "auto"),
                                  (50000, "path", "auto"), (50000, "cycle", "auto"),
                                  (50000, "unique", "auto"), (1024, "path", "trace")]:
        row = {"case": f"synthetic-{topology}-{nodes}", "kind": "synthetic", "nodes": nodes,
               **measure(case(nodes, topology), args.repetitions, mode)}
        rows.append(row)
        print(row["case"], {x["status"] for x in row["observations"]}, round(row["median_seconds"], 3), row["maximum_sampled_peak_mb"], flush=True)
    if args.root:
        for name in ("PROTEINS", "ENZYMES"):
            raw = (args.root / name / "audit" / "training.json").read_text(encoding="utf-8")
            row = {"case": name, "kind": "actual_training_inputs", **measure(raw, args.repetitions)}
            rows.append(row)
            print(name, {x["status"] for x in row["observations"]}, round(row["median_seconds"], 3), row["maximum_sampled_peak_mb"], flush=True)
    result = {"kind": "isolated_service_scale_probe", "environment": {"python": platform.python_version(), "platform": platform.platform()},
              "limits": asdict(Limits()), "repetitions": args.repetitions, "cases": rows,
              "interpretation": "Local probes include process startup, exact refinement, independent replay, all four artifacts and streamed reads. RSS is sampled, so may miss the true peak. Three repetitions are not a production p95 or throughput claim. Resource limits may reject difficult inputs below the node cap; rejected jobs publish no ceiling. Real inputs use the contract in real-data-study.json; no model training or held-out evaluation occurs."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
