"""Reproducible synthetic capacity probes; these are not ML dataset studies."""

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


def case(n, topology):
    edges = [[str(i), str(i + 1)] for i in range(n - 1)]
    if topology == "cycle":
        edges.append([str(n - 1), "0"])
    features = [[i] if topology == "unique" else [1] for i in range(n)]
    return json.dumps({"schema_version": 1, "split": "train", "graph_type": "simple_undirected",
                       "feature_dtype": "float64", "feature_dim": 1,
                       "graphs": [{"id": topology + str(n), "label": 0,
                                   "nodes": [{"id": str(i), "features": features[i]} for i in range(n)], "edges": edges}]})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/performance.json"))
    parser.add_argument("--repetitions", type=int, default=5)
    args=parser.parse_args()
    limits=Limits()
    rows=[]
    for n, topology in [(128,"path"),(512,"cycle"),(2048,"cycle"),(512,"unique"),(1024,"path")]:
        observations=[]
        for _ in range(args.repetitions):
            manager=JobManager(limits)
            try:
                started=time.monotonic()
                job=manager.submit(case(n,topology))
                while job["status"] in {"queued","running"}:
                    time.sleep(.01)
                    job=manager.get(job["id"])
                observations.append({"status": job["status"], "wall_seconds": time.monotonic()-started,
                                     "worker_seconds": job["runtime_seconds"], "sampled_peak_mb": job["peak_memory_mb"],
                                     "round": (job["progress"] or {}).get("round"), "error": job["error"]})
            finally:
                manager.close()
        times=sorted(item["wall_seconds"] for item in observations)
        rows.append({"nodes": n, "topology": topology, "observations": observations,
                     "median_seconds": statistics.median(times), "max_seconds": max(times),
                     "maximum_sampled_peak_mb": max(item["sampled_peak_mb"] for item in observations)})
    result={"kind": "synthetic_service_capacity_probe", "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "limits": asdict(limits), "repetitions": args.repetitions, "cases": rows,
            "interpretation": "Small synthetic probes include process startup, refinement, independent replay and artifact serialization. Sampled RSS is a lower bound on the true peak. Five repetitions do not establish production p95 or throughput. Rejected jobs have no certified ceiling."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    for row in rows:
        print(row["topology"],row["nodes"],{x["status"] for x in row["observations"]},round(row["median_seconds"],3),row["maximum_sampled_peak_mb"])


if __name__=="__main__":
    main()
