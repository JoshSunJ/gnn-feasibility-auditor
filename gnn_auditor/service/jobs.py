"""Bounded, ephemeral jobs supervised outside the request event loop."""

from dataclasses import dataclass, field
import multiprocessing as mp
from pathlib import Path
import secrets
import shutil
import tempfile
import threading
import time
from typing import Any

import psutil

from .limits import Limits
from .worker import run_audit

TERMINAL = {"completed", "rejected", "timed_out", "cancelled", "failed"}


class CapacityError(ValueError):
    pass


@dataclass
class Job:
    id: str
    raw: str | None
    directory: Path
    status: str = "queued"
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    progress: dict | None = None
    summary: dict | None = None
    error: dict | None = None
    process: Any = None
    connection: Any = None
    peak_bytes: int = 0
    duration: float = 0
    mode: str = "auto"


class JobManager:
    def __init__(self, limits: Limits, *, worker=run_audit):
        self.limits = limits
        self.worker = worker
        self.context = mp.get_context("spawn")
        self.root = tempfile.TemporaryDirectory(prefix="gnn-auditor-")
        self.jobs: dict[str, Job] = {}
        self.lock = threading.RLock()
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._supervise, name="audit-supervisor", daemon=True)
        self.thread.start()

    def can_submit(self):
        with self.lock:
            self._expire()
            admitted = sum(j.status in {"queued", "running"} for j in self.jobs.values())
            return not self.closed.is_set() and admitted < self.limits.max_active + self.limits.max_queued and len(self.jobs) < self.limits.max_retained

    def submit(self, raw: str, mode: str = "auto") -> dict:
        if mode not in {"auto", "trace", "partition"}:
            raise ValueError("unsupported audit mode")
        with self.lock:
            self._expire()
            if not self.can_submit():
                raise CapacityError("Audit capacity is full. Download existing results or retry after temporary jobs expire.")
            job_id = secrets.token_urlsafe(32)
            directory = Path(self.root.name, job_id)
            directory.mkdir(mode=0o700)
            job = Job(job_id, raw, directory, mode=mode)
            self.jobs[job_id] = job
            return self._view(job)

    def get(self, job_id: str) -> dict:
        with self.lock:
            self._expire()
            return self._view(self.jobs[job_id])

    def cancel(self, job_id: str) -> dict:
        with self.lock:
            self._expire()
            job = self.jobs[job_id]
            if job.status not in TERMINAL:
                self._finish(job, "cancelled", {"code": "cancelled", "message": "Audit cancelled. No ceiling was certified."})
            return self._view(job)

    def artifact(self, job_id: str, name: str) -> bytes:
        with self.open_artifact(job_id, name) as stream:
            return stream.read()

    def open_artifact(self, job_id: str, name: str):
        with self.lock:
            self._expire()
            job = self.jobs[job_id]
            if job.status != "completed":
                raise ValueError("Artifacts are available only after a completed, independently verified audit.")
            return Path(job.directory, {"report": "report.json", "inputs": "inputs.json", "explorer": "explorer.html", "view": "view.json"}[name]).open("rb")

    def health(self):
        with self.lock:
            return {"status": "ok" if not self.closed.is_set() else "stopping",
                    "active": sum(j.status == "running" for j in self.jobs.values()),
                    "queued": sum(j.status == "queued" for j in self.jobs.values())}

    def _view(self, job):
        return {"id": job.id, "status": job.status, "created_at": job.created,
                "expires_at": (job.finished + self.limits.ttl_seconds) if job.finished else None,
                "progress": job.progress, "summary": job.summary if job.status == "completed" else None,
                "error": job.error, "runtime_seconds": job.duration,
                "peak_memory_mb": round(job.peak_bytes / 1024**2, 2)}

    def _stop(self, job):
        if job.process is not None:
            if job.process.is_alive():
                job.process.terminate()
            job.process.join(timeout=.2)
            if job.process.is_alive():
                job.process.kill()
                job.process.join(timeout=.2)
            job.process.close()
            job.process = None
        if job.connection is not None:
            job.connection.close()
            job.connection = None

    def _finish(self, job, status, error=None):
        job.status, job.error = status, error
        job.finished = time.time()
        if job.started is not None:
            job.duration = time.monotonic() - job.started
        job.raw = None
        self._stop(job)
        if status != "completed":
            job.summary = None
            shutil.rmtree(job.directory, ignore_errors=True)

    def _expire(self):
        now = time.time()
        for job in list(self.jobs.values()):
            if job.finished is not None and now >= job.finished + self.limits.ttl_seconds:
                shutil.rmtree(job.directory, ignore_errors=True)
                del self.jobs[job.id]

    def _tick(self):
        with self.lock:
            self._expire()
            for job in list(self.jobs.values()):
                if job.status != "running":
                    continue
                job.duration = time.monotonic() - job.started
                try:
                    rss = psutil.Process(job.process.pid).memory_info().rss
                    job.peak_bytes = max(job.peak_bytes, rss)
                except psutil.Error:
                    pass
                if job.duration >= self.limits.timeout_seconds:
                    self._finish(job, "timed_out", {"code": "timeout", "message": "Audit time budget exceeded. No ceiling was certified."})
                    continue
                if job.peak_bytes > self.limits.memory_mb * 1024**2:
                    self._finish(job, "rejected", {"code": "resource_limit", "message": "Audit memory budget exceeded. No ceiling was certified."})
                    continue
                try:
                    while job.connection is not None and job.connection.poll():
                        event = job.connection.recv()
                        kind = event["kind"]
                        if kind == "progress":
                            job.progress = {"round": event.get("round"), "step": event.get("step"), "color_count": event["color_count"]}
                        elif kind == "completed":
                            if not all((job.directory / name).is_file() for name in ("report.json", "inputs.json", "explorer.html", "view.json")):
                                raise ValueError("missing verified artifacts")
                            job.summary = event["summary"]
                            self._finish(job, "completed")
                        else:
                            self._finish(job, kind, {"code": event["code"], "message": event["message"]})
                except (EOFError, OSError):
                    pass
                except Exception:
                    self._finish(job, "failed", {"code": "worker_failed", "message": "Audit worker failed. No ceiling was certified."})
                if job.status == "running" and not job.process.is_alive():
                    self._finish(job, "failed", {"code": "worker_exited", "message": "Audit worker exited before verification. No ceiling was certified."})
            active = sum(j.status == "running" for j in self.jobs.values())
            for job in self.jobs.values():
                if active >= self.limits.max_active:
                    break
                if job.status != "queued":
                    continue
                parent, child = self.context.Pipe(duplex=False)
                job.connection = parent
                job.process = self.context.Process(target=self.worker, args=({"raw": job.raw, "mode": job.mode}, str(job.directory), self.limits, child), daemon=True)
                try:
                    job.started = time.monotonic()
                    job.process.start()
                    job.raw = None
                    job.status = "running"
                    active += 1
                except Exception:
                    parent.close()
                    job.connection = None
                    job.process = None
                    self._finish(job, "failed", {"code": "worker_start_failed", "message": "Audit worker could not start. No ceiling was certified."})
                finally:
                    child.close()

    def _supervise(self):
        while not self.closed.wait(.02):
            self._tick()

    def close(self):
        self.closed.set()
        self.thread.join(timeout=2)
        with self.lock:
            for job in self.jobs.values():
                self._stop(job)
            self.jobs.clear()
            self.root.cleanup()
