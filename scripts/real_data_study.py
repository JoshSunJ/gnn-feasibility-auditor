"""Reproduce actual-feature training audits from original TU datasets.

Raw data stays in the selected work directory. Only aggregate results and source
provenance are committed; digests identify artifacts, never prove WL equivalence.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import random
import resource
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gnn_auditor.data import dataset_object
from gnn_auditor.partition import audit_partition
from gnn_auditor.pyg import dataset_from_pyg
from gnn_auditor.verify import verify_report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=Path("docs/real-data-study.json"))
    parser.add_argument("--datasets",nargs="+",default=["PROTEINS","ENZYMES"],choices=["PROTEINS","ENZYMES"])
    args=parser.parse_args()
    import torch
    import torch_geometric
    from torch_geometric.datasets import TUDataset
    rows=[]
    for name in args.datasets:
        source=TUDataset(str(args.root/name),name,use_node_attr=True,use_edge_attr=True,cleaned=False)
        positions=list(range(len(source)))
        random.Random(20261012).shuffle(positions)
        training=sorted(positions[:int(.8*len(source))])
        data=dataset_from_pyg(source,train_indices=training)
        represented=dataset_object(data)
        work=args.root/name/"audit"
        work.mkdir(parents=True,exist_ok=True)
        input_path=work/"training.json"
        input_path.write_text(json.dumps(represented,separators=(",",":"),allow_nan=False)+"\n")
        started=time.perf_counter()
        report=audit_partition(data,include_certificate=True)
        audit_seconds=time.perf_counter()-started
        started=time.perf_counter()
        verify_report(data,json.loads(json.dumps(report)))
        replay_seconds=time.perf_counter()-started
        (work/"report.json").write_text(json.dumps(report,separators=(",",":"),allow_nan=False)+"\n")
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_mb=peak/(1024**2 if sys.platform=="darwin" else 1024)
        raw_files={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(Path(source.raw_dir).glob("*.txt"))}
        row={"dataset":name,"source_url":f"https://www.chrsmrrs.com/graphkerneldatasets/{name}.zip",
             "catalogue_url":"https://chrsmrrs.github.io/datasets/docs/datasets/",
             "total_source_graphs":len(source),"training_graphs":len(training),"train_indices":training,
             "training_selection":{"seed":20261012,"method":"shuffle all positions, select first floor(0.8*N), sort selected positions","held_out_graphs_audited":False},
             "loader":{"use_node_attr":True,"use_edge_attr":True,"cleaned":False,"transforms":None},
             "input_contract":{"feature_dtype":data.feature_dtype,"feature_dim":data.feature_dim,
                 "features":"PyG x includes supplied continuous node attributes and one-hot supplied node labels; no replacement constants, degrees, binning or positional features",
                 "topology":"actual simple undirected edge_index produced by the recorded PyG TU loader; default loader removes self-loops/coalesces COO entries before model consumption",
                 "model_uses":["x","edge_index"],"edge_attributes_present":False,"extra_model_inputs":False},
             "training_label_counts":dict(Counter(str(g.label) for g in data.graphs)),
             "node_count":report["node_count"],"edge_count":report["edge_count"],"class_count":report["class_count"],
             "bound":report["training_accuracy_upper_bound"],"unavoidable_training_errors":report["unavoidable_training_errors"],
             "conflicting_pair_count":report["conflicting_pair_count"],"certificate_verified":True,
             "audit_seconds":audit_seconds,"independent_replay_seconds":replay_seconds,
             "process_peak_rss_mb":peak_mb,"peak_scope":"cumulative process peak including PyTorch/PyG loading, not isolated serving-worker memory",
             "input_bytes":input_path.stat().st_size,"certificate_report_bytes":(work/"report.json").stat().st_size,
             "initial_colors":report["initial_color_count"],"final_colors":report["final_color_count"],
             "producer_work":report["producer_work"],"raw_file_sha256_for_provenance_only":raw_files,
             "interpretation":"Training input audit only. 100% is inconclusive; no claim about optimizer success, held-out accuracy, or real-model training is made."}
        rows.append(row)
        print(name,row["training_graphs"],row["node_count"],row["bound"]["fraction"],round(audit_seconds,3),round(replay_seconds,3),flush=True)
    result={"study_version":1,"environment":{"python":platform.python_version(),"platform":platform.platform(),"torch":torch.__version__,"pyg":torch_geometric.__version__},"cases":rows,
            "redistribution":"Raw training inputs and certificates are regenerated under --root and are not committed. Aggregate results, source links and provenance digests are committed."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")


if __name__=="__main__":main()
