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
