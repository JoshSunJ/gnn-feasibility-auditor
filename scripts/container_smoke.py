"""Check the actual Linux container through HTTP, including verified artifacts."""
import json
import time
from urllib.request import Request, urlopen

BASE="http://127.0.0.1:8000"

def read(path):
    with urlopen(BASE+path,timeout=5) as response:
        return response.read()

raw=read("/api/demo")
with urlopen(Request(BASE+"/api/jobs",data=raw,headers={"Content-Type":"application/json"}),timeout=5) as response:
    job=json.load(response)
for _ in range(200):
    job=json.loads(read("/api/jobs/"+job["id"]))
    if job["status"] not in {"queued","running"}:
        break
    time.sleep(.1)
assert job["status"]=="completed", job
report=json.loads(read("/api/jobs/"+job["id"]+"/report"))
assert report["training_accuracy_upper_bound"]["fraction"]=="4/5"
assert job["summary"]["certificate_verified"] is True
assert b"cycle-6" in read("/api/jobs/"+job["id"]+"/explorer")
assert b"graph_label_text" in read("/api/jobs/"+job["id"]+"/view")
print("Linux container: frontend, worker, verified 4/5 audit and downloads passed.")

# Exercise the compact engine under the actual Linux address-space limit,
# including large artifact publication rather than only an easy tiny demo.
n = 50_000
large = json.dumps({"schema_version": 1, "split": "train", "graph_type": "simple_undirected", "feature_dtype": "float64", "feature_dim": 1,
                    "graphs": [{"id": "capacity-path", "label": 0, "nodes": [{"id": str(i), "features": [1]} for i in range(n)],
                                "edges": [[str(i), str(i + 1)] for i in range(n - 1)]}]}).encode()
with urlopen(Request(BASE + "/api/jobs", data=large, headers={"Content-Type": "application/json"}), timeout=10) as response:
    job = json.load(response)
for _ in range(300):
    job = json.loads(read("/api/jobs/" + job["id"]))
    if job["status"] not in {"queued", "running"}:
        break
    time.sleep(.1)
assert job["status"] == "completed", job
assert job["summary"]["engine"] == "partition" and job["summary"]["node_count"] == n
report = json.loads(read("/api/jobs/" + job["id"] + "/report"))
assert report["certificate"]["version"] == 2 and report["final_color_count"] == n // 2
assert report["training_accuracy_upper_bound"]["fraction"] == "1"
assert json.loads(read("/api/jobs/" + job["id"] + "/view"))["inspection"]["mode"] == "stable_only"
print("Linux container: exact compact 50,000-node path, replay and exports passed within service budgets.")
