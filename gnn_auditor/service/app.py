"""Same-origin HTTP interface. Upload text goes unchanged to the strict loader."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import anyio

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .jobs import CapacityError, JobManager
from .limits import Limits


class Progress(BaseModel):
    round: int
    color_count: int


class JobView(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "rejected", "timed_out", "cancelled", "failed"]
    created_at: float
    expires_at: float | None
    progress: Progress | None
    summary: dict | None
    error: dict | None
    runtime_seconds: float
    peak_memory_mb: float


def create_app(limits: Limits | None = None, *, manager_factory=JobManager, frontend: Path | None = None):
    limits = limits or Limits.from_env()
    root = Path(__file__).resolve().parents[2]
    frontend = frontend or root / "frontend" / "dist"

    @asynccontextmanager
    async def lifespan(app):
        app.state.jobs = manager_factory(limits)
        yield
        app.state.jobs.close()

    app = FastAPI(title="GNN Feasibility Auditor", version="0.2.0", lifespan=lifespan,
                  description="Exact actual-feature 1-WL auditing of supplied training graphs. Completed results are independently replayed; interrupted jobs have no certified ceiling.")

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        return response

    @app.get("/api/health")
    def health():
        return app.state.jobs.health()

    @app.get("/api/config")
    def config():
        return {"limits": limits.public(), "scope": "simple undirected training graphs with explicit numeric float32/float64 node features", "storage": "Temporary; results expire and are lost on service restart.", "version": "0.2.0"}

    @app.get("/api/demo")
    def demo():
        # Packaged demo, no network dataset download or synthesized features.
        return FileResponse(Path(__file__).with_name("demo.json"), media_type="application/json")

    @app.post("/api/jobs", status_code=202, response_model=JobView)
    async def submit(request: Request):
        if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
            raise HTTPException(415, "Send the original dataset JSON with Content-Type: application/json.")
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > limits.max_bytes:
                    raise HTTPException(413, "Dataset exceeds this service's upload byte limit.")
            except ValueError:
                raise HTTPException(400, "Invalid Content-Length.")
        body = bytearray()
        try:
            with anyio.fail_after(10):
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > limits.max_bytes:
                        raise HTTPException(413, "Dataset exceeds this service's upload byte limit.")
        except TimeoutError:
            raise HTTPException(408, "Upload took too long. Retry with a smaller file.")
        try:
            raw = body.decode("utf-8")
        except UnicodeError:
            raise HTTPException(400, "Dataset must be UTF-8 JSON.")
        try:
            return app.state.jobs.submit(raw)
        except CapacityError as error:
            raise HTTPException(429, str(error), headers={"Retry-After": "10"})

    def lookup(action, *args):
        try:
            return action(*args)
        except KeyError:
            raise HTTPException(404, "Job unavailable: unknown, expired, or lost on restart. Run a new audit.")
        except ValueError as error:
            raise HTTPException(409, str(error))

    @app.get("/api/jobs/{job_id}", response_model=JobView)
    def status(job_id: str):
        return lookup(app.state.jobs.get, job_id)

    @app.delete("/api/jobs/{job_id}", response_model=JobView)
    def cancel(job_id: str):
        return lookup(app.state.jobs.cancel, job_id)

    @app.get("/api/jobs/{job_id}/{artifact}")
    def download(job_id: str, artifact: str):
        if artifact not in {"report", "inputs", "explorer", "view"}:
            raise HTTPException(404, "Unknown artifact.")
        content = lookup(app.state.jobs.artifact, job_id, artifact)
        if artifact == "explorer":
            return Response(content, media_type="text/html")
        headers = {} if artifact == "view" else {"Content-Disposition": f'attachment; filename="{artifact}.json"'}
        return Response(content, media_type="application/json", headers=headers)

    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
