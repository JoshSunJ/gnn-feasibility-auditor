"""Service integration tests exercise real spawned workers and interrupted jobs."""

import importlib.util
import json
from pathlib import Path
import time
import unittest

AVAILABLE = all(importlib.util.find_spec(name) for name in ("fastapi", "httpx", "psutil"))
if AVAILABLE:
    from fastapi.testclient import TestClient
    from gnn_auditor.data import loads_dataset
    from gnn_auditor.report import audit
    from gnn_auditor.service.app import create_app
    from gnn_auditor.service.jobs import JobManager
    from gnn_auditor.service.limits import Limits
    from gnn_auditor.verify import verify_report

RAW = Path(__file__).resolve().parents[1].joinpath("examples/conflicts.json").read_text()


def sleepy_worker(raw, directory, limits, connection):
    time.sleep(5)


def exiting_worker(raw, directory, limits, connection):
    connection.close()


def wait_job(client, job_id, wanted=None):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        if job["status"] == wanted or (wanted is None and job["status"] not in {"queued", "running"}):
            return job
        time.sleep(.02)
    raise AssertionError("job did not reach expected state")


@unittest.skipUnless(AVAILABLE, "optional service/test dependencies are not installed")
class ServiceTests(unittest.TestCase):
    def submit(self, client, raw=RAW):
        response = client.post("/api/jobs", content=raw, headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()["id"]

    def test_completed_matches_cli_and_replays_exact_download(self):
        with TestClient(create_app()) as client:
            self.assertEqual(client.get("/api/health").status_code, 200)
            self.assertEqual(client.get("/api/demo").text, RAW)
            job_id = self.submit(client)
            job = wait_job(client, job_id)
            self.assertEqual(job["status"], "completed", job)
            self.assertTrue(job["summary"]["certificate_verified"])
            response = client.get(f"/api/jobs/{job_id}/report")
            self.assertEqual(response.headers["cache-control"], "no-store")
            report = response.json()
            dataset = loads_dataset(client.get(f"/api/jobs/{job_id}/inputs").text)
            self.assertEqual(report, json.loads(json.dumps(audit(dataset, max_pairs=100, include_certificate=True))))
            verify_report(dataset, report)
            self.assertIn("cycle-6", client.get(f"/api/jobs/{job_id}/explorer").text)
            self.assertEqual(job["summary"]["training_accuracy_upper_bound"]["fraction"], "4/5")
            self.assertGreater(job["runtime_seconds"], 0)

    def test_duplicate_keys_and_unsupported_inputs_rejected_without_artifact(self):
        with TestClient(create_app()) as client:
            for raw in ('{"graphs":[],"graphs":[]}', RAW.replace('"simple_undirected"', '"directed"')):
                job_id = self.submit(client, raw)
                job = wait_job(client, job_id)
                self.assertEqual(job["status"], "rejected")
                self.assertEqual(job["error"]["code"], "invalid_input")
                self.assertIsNone(job["summary"])
                self.assertEqual(client.get(f"/api/jobs/{job_id}/report").status_code, 409)

    def test_wire_bytes_and_utf8_are_bounded(self):
        with TestClient(create_app(Limits(max_bytes=64))) as client:
            self.assertEqual(client.post("/api/jobs", content="{}", headers={"Content-Type": "text/plain"}).status_code, 415)
            self.assertEqual(client.post("/api/jobs", content=RAW, headers={"Content-Type": "application/json"}).status_code, 413)
            self.assertEqual(client.post("/api/jobs", content=iter([b" " * 40, b" " * 40]), headers={"Content-Type": "application/json"}).status_code, 413)
            self.assertEqual(client.post("/api/jobs", content=b"\xff", headers={"Content-Type": "application/json"}).status_code, 400)

    def test_dataset_trace_and_output_budget_never_publish_partial_result(self):
        for limits in (Limits(max_graphs=2), Limits(max_trace_cells=2), Limits(max_output_bytes=100)):
            with self.subTest(limits=limits), TestClient(create_app(limits)) as client:
                job_id = self.submit(client)
                job = wait_job(client, job_id)
                self.assertEqual(job["status"], "rejected", job)
                self.assertEqual(job["error"]["code"], "resource_limit")
                self.assertIsNone(job["summary"])
                self.assertEqual(client.get(f"/api/jobs/{job_id}/explorer").status_code, 409)

    def test_running_cancel_and_overload(self):
        limits = Limits(max_active=1, max_queued=1, max_retained=2)
        factory = lambda value: JobManager(value, worker=sleepy_worker)
        with TestClient(create_app(limits, manager_factory=factory)) as client:
            first = self.submit(client)
            wait_job(client, first, "running")
            second = self.submit(client)
            overloaded = client.post("/api/jobs", content=RAW, headers={"Content-Type": "application/json"})
            self.assertEqual(overloaded.status_code, 429)
            self.assertEqual(overloaded.headers["retry-after"], "10")
            for job_id in (second, first):
                job = client.delete(f"/api/jobs/{job_id}").json()
                self.assertEqual(job["status"], "cancelled")
                self.assertIsNone(job["summary"])
                self.assertEqual(client.get(f"/api/jobs/{job_id}/report").status_code, 409)
            self.assertEqual(client.get("/api/health").json()["active"], 0)

    def test_timeout_memory_and_unexpected_exit(self):
        cases = [(Limits(timeout_seconds=.05), sleepy_worker, "timed_out"),
                 (Limits(memory_mb=1), sleepy_worker, "rejected"),
                 (Limits(), exiting_worker, "failed")]
        for limits, worker, status in cases:
            with self.subTest(status=status), TestClient(create_app(limits, manager_factory=lambda value: JobManager(value, worker=worker))) as client:
                job_id = self.submit(client)
                job = wait_job(client, job_id)
                self.assertEqual(job["status"], status, job)
                self.assertIsNone(job["summary"])
                self.assertEqual(client.get(f"/api/jobs/{job_id}/report").status_code, 409)

    def test_expiry_and_restart_do_not_recover_results(self):
        with TestClient(create_app(Limits(ttl_seconds=.1))) as client:
            job_id = self.submit(client)
            self.assertEqual(wait_job(client, job_id)["status"], "completed")
            time.sleep(.15)
            self.assertEqual(client.get(f"/api/jobs/{job_id}").status_code, 404)
        with TestClient(create_app()) as client:
            self.assertEqual(client.get(f"/api/jobs/{job_id}").status_code, 404)

    def test_big_integer_labels_remain_exact_in_downloads(self):
        raw = RAW.replace('"connected"', '900719925474099312345')
        with TestClient(create_app()) as client:
            job_id = self.submit(client, raw)
            self.assertEqual(wait_job(client, job_id)["status"], "completed")
            self.assertIn("900719925474099312345", client.get(f"/api/jobs/{job_id}/report").text)
            self.assertIn("900719925474099312345", client.get(f"/api/jobs/{job_id}/inputs").text)

    def test_shutdown_reaps_children_and_removes_temporary_data(self):
        manager = JobManager(Limits(), worker=sleepy_worker)
        path = Path(manager.root.name)
        job_id = manager.submit(RAW)["id"]
        deadline = time.monotonic() + 2
        while manager.get(job_id)["status"] != "running" and time.monotonic() < deadline:
            time.sleep(.02)
        child = manager.jobs[job_id].process.pid
        manager.close()
        self.assertFalse(path.exists())
        import psutil
        self.assertFalse(psutil.pid_exists(child))
