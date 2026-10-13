import copy
from itertools import combinations
import json
import math
import random
import unittest

from gnn_auditor.data import parse_dataset, load_dataset
from gnn_auditor.partition import audit_partition, refine_partition
from gnn_auditor.refinement import refine
from gnn_auditor.report import audit
from gnn_auditor.verify import VerificationError, verify_report
from test_core import graph, dataset, reference_pair


class PartitionTests(unittest.TestCase):
    def test_both_certificate_versions_reject_cross_type_label_metadata(self):
        data = parse_dataset(dataset(graph("a", 1, [], 0), graph("b", 1, [], 1)))
        for engine in (audit, audit_partition):
            original = engine(data, include_certificate=True)
            verify_report(data, original)
            for field in ("label_counts", "majority_labels"):
                for replacement in (False, 0.0):
                    report = copy.deepcopy(original)
                    report["classes"][0][field][0]["label"] = replacement
                    with self.subTest(engine=engine.__name__, field=field, replacement=replacement), self.assertRaisesRegex(VerificationError, "label type"):
                        verify_report(data, report)
            report = copy.deepcopy(original)
            report["classes"][0]["label_counts"][0]["count"] = True
            with self.assertRaisesRegex(VerificationError, "count must be an integer"):
                verify_report(data, report)

    def test_all_5265_oracle_pairs(self):
        small = []
        for n in range(5):
            possible = list(combinations(range(n), 2))
            for mask in range(1 << len(possible)):
                small.append(graph(f"n{n}-{mask}", n, [e for i,e in enumerate(possible) if mask & (1 << i)]))
        rng = random.Random(20261010)
        random_graphs = []
        for i in range(60):
            n = rng.randrange(0,9)
            random_graphs.append(graph(str(i), n, [e for e in combinations(range(n),2) if rng.random()<.3], features=[[rng.choice([0.,1.,2.])] for _ in range(n)]))
        for i in range(10):
            duplicate=copy.deepcopy(random_graphs[i]);duplicate["id"]="copy-"+str(i);random_graphs.append(duplicate)
        pairs=0
        for items in (small,random_graphs):
            data=parse_dataset(dataset(*items))
            final=refine_partition(data).histograms
            for i,j in combinations(range(len(items)),2):
                self.assertEqual(final[i]==final[j],reference_pair(data.graphs[i],data.graphs[j]),(items[i]["id"],items[j]["id"]))
                pairs+=1
            verify_report(data,json.loads(json.dumps(audit_partition(data,include_certificate=True))))
        self.assertEqual(pairs,5265)

    def test_demo_matches_original_arithmetic_and_classes(self):
        data=load_dataset("examples/conflicts.json")
        old=audit(data)
        new=audit_partition(data,include_certificate=True)
        for key in ("training_accuracy_upper_bound","unavoidable_training_errors","conflicting_pair_count","class_count"):
            self.assertEqual(new[key],old[key])
        memberships=lambda r:{tuple(c["graph_ids"]) for c in r["classes"]}
        self.assertEqual(memberships(new),memberships(old))
        self.assertNotIn("rounds",new)
        self.assertNotIn("stabilization_round",new)
        verify_report(data,json.loads(json.dumps(new)))

    def test_permutation_feature_precision_and_labels(self):
        raw=dataset(graph("a",4,[(0,1),(1,2),(2,3)],"one",[[0],[1],[1],[0]]),graph("b",4,[(0,1),(1,2),(2,3)],"two",[[0],[1],[1],[0]]))
        original=audit_partition(parse_dataset(raw),include_certificate=True)
        altered=copy.deepcopy(raw)
        for g in altered["graphs"]:
            for node in g["nodes"]:node["id"]="n"+node["id"]
            g["nodes"].reverse();g["edges"]=[["n"+v,"n"+u] for u,v in reversed(g["edges"])]
        changed=audit_partition(parse_dataset(altered),include_certificate=True)
        self.assertEqual(original["classes"],changed["classes"])
        verify_report(parse_dataset(altered),changed)
        altered["graphs"][0]["label"]="two"
        self.assertEqual(refine_partition(parse_dataset(raw)).histograms,refine_partition(parse_dataset(altered)).histograms)
        a=graph("a",1,[],features=[[1.]])
        b=graph("b",1,[],features=[[math.nextafter(1.,2.)]])
        self.assertEqual(audit_partition(parse_dataset(dataset(a,b)))["class_count"],2)
        self.assertEqual(audit_partition(parse_dataset(dataset(a,b,dtype="float32")))["class_count"],1)
        a["nodes"][0]["features"]=[-0.];b["nodes"][0]["features"]=[0.]
        self.assertEqual(audit_partition(parse_dataset(dataset(a,b)))["class_count"],1)

    def test_replay_rejects_tamper_early_stop_and_arbitrary_individualization(self):
        data=parse_dataset(dataset(graph("path",10,[(i,i+1) for i in range(9)])))
        report=json.loads(json.dumps(audit_partition(data,include_certificate=True)))
        for mutate in (
            lambda r:r["certificate"]["events"].pop(),
            lambda r:r["certificate"]["events"][0].update(splitter=999),
            lambda r:r["certificate"]["events"][0]["splits"][0]["moved"][0]["vertices"].pop(),
            lambda r:r["certificate"]["events"][0]["splits"][0]["moved"][0].update(count=42),
            lambda r:r["training_accuracy_upper_bound"].update(max_correct=42),
            lambda r:r["classes"][0]["label_counts"][0].update(label="changed"),
        ):
            bad=copy.deepcopy(report);mutate(bad)
            with self.assertRaises(VerificationError):verify_report(data,bad)
        isolates=parse_dataset(dataset(graph("isolates",2,[])))
        bad=audit_partition(isolates,include_certificate=True)
        bad["certificate"]["events"]=[{"splitter":0,"splits":[{"cell":0,"retained_count":0,"moved":[{"count":0,"vertices":[0]}]}]}]
        bad["certificate"]["final_node_colors"]=[[0,1]]
        with self.assertRaises(VerificationError):verify_report(isolates,bad)

    def test_empty_graphs_zero_dim_and_long_path_compact_evidence(self):
        data=parse_dataset(dataset(graph("a",0,[],"x"),graph("b",0,[],"y")))
        report=audit_partition(data,include_certificate=True);verify_report(data,report)
        self.assertEqual(report["training_accuracy_upper_bound"]["fraction"],"1/2")
        zero=parse_dataset(dataset(graph("a",2,[(0,1)],features=[[],[]]),dim=0))
        verify_report(zero,audit_partition(zero,include_certificate=True))
        n=6000
        path=parse_dataset(dataset(graph("long",n,[(i,i+1) for i in range(n-1)])))
        result=refine_partition(path)
        self.assertLess(result.edge_visits,20*n)
        self.assertLess(result.moved_vertices,2*n)
        report=audit_partition(path,include_certificate=True)
        verify_report(path,json.loads(json.dumps(report)))
        self.assertEqual(report["final_color_count"],n//2)

    def test_callback_interrupt_cannot_return_partial_summary(self):
        data=parse_dataset(dataset(graph("p",6,[(i,i+1) for i in range(5)])))
        def interrupt(step):raise RuntimeError("budget exhausted")
        with self.assertRaises(RuntimeError):audit_partition(data,include_certificate=True,on_step=interrupt)
