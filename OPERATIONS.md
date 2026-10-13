# Operating the SWE application

## Architecture and job lifecycle

One Uvicorn API process serves the built React assets and HTTP endpoints. A supervisor thread admits a bounded queue and starts independent spawned Python workers. CPU work runs outside the request event loop. Each job uses an unguessable identifier and a private temporary directory.

`queued → running → completed | rejected | timed_out | cancelled | failed`

Only `completed` jobs expose artifacts. A worker loads the original JSON text with the strict core loader, checks input budgets, refines to stability, independently replays the certificate, serializes bounded artifacts, and then publishes completion. A refinement-budget exception never becomes a partial WL match or a training ceiling.

Cancellation terminates the worker and removes partial artifacts. Runtime and RSS watchdogs supervise execution; Linux workers also have an address-space limit. Admission is bounded across the whole single process. Multiple Uvicorn workers would create independent queues and violate the intended global capacity; use exactly one worker.

The HTTP server caps concurrent requests at 32 in Docker, and uploads have a 10-second read deadline and an enforced streamed byte limit. Job overload returns 429 with Retry-After. Server connection overload can return 503. This anonymous demonstration service has no fairness guarantees or durable scheduler.

## API

| Endpoint | Behavior |
|---|---|
| `GET /api/health` | Readiness and active/queued counts; no dataset identifiers |
| `GET /api/config` | Public input/execution budgets and scope |
| `GET /api/demo` | Packaged synthetic fixture |
| `POST /api/jobs` | Original UTF-8 JSON body; Content-Type application/json; 202 admission |
| `GET /api/jobs/{id}` | State, actual round/color progress, completed summary or readable failure |
| `DELETE /api/jobs/{id}` | Cancel queued/running work; terminal jobs remain terminal |
| `GET /api/jobs/{id}/report` | Exact JSON report and certificate download |
| `GET /api/jobs/{id}/inputs` | Exact represented input JSON download |
| `GET /api/jobs/{id}/explorer` | Self-contained verified HTML report |
| `GET /api/jobs/{id}/view` | Inspection payload, including exact textual labels for JavaScript display |

Wrong media type: 415; oversized upload: 413; unreadable encoding: 400; admission overload: 429; unavailable job: 404; unfinished artifact: 409. Schema validation runs in the isolated worker and returns a rejected job with field context. A rejected admission or worker is not a certified audit.

Do not parse/reserialize datasets through JavaScript before submitting: doing so could alter large integer labels or erase duplicate keys. Downloads use the server's exact JSON bytes. The inspection view uses parallel label strings to avoid JavaScript integer rounding.

## Default budgets

| Budget | Default |
|---|---:|
| Upload bytes | 1 MiB |
| Graphs / total nodes / total edges | 128 / 2,048 / 8,192 |
| Feature dimension | 64 |
| Cumulative node-round trace cells | 131,072 |
| Total serialized artifacts | 16 MiB |
| Worker wall time / memory | 20 seconds / 256 MiB |
| Active workers / queued jobs | 1 / 3 |
| Retained jobs | 8 |
| Terminal-result retention | 15 minutes |

These are admission ceilings, not promises that every input below them completes. Difficult refinement or large artifacts can hit a later budget. Override through `AUDITOR_` plus the uppercase field name in `gnn_auditor/service/limits.py`. Validate changed settings with the capacity probe and failure suite; instance-level memory must cover the API plus all workers and downloads.

The browser draws topology up to 500 nodes per graph; larger graphs retain all audited inputs and can be inspected through node selection and exports. Display limits never alter the audit.

## Privacy, expiry and restart

No accounts or persistent dataset history are implemented. Job URLs are bearer capabilities: anyone with a URL can inspect its result until expiry. No job list is exposed. Responses are not cached; the page sets no-referrer and same-origin framing policies. Inputs and results are temporary files and disappear on expiry or shutdown. A restart loses every job; clients receive an unavailable/expired/restarted message and must submit again.

Uvicorn access logging is disabled so capability URLs and dataset details do not enter request logs. Worker failures return fixed internal-error messages. No uploaded model files, executable files or pickles are accepted. Audit inputs are always numeric, declarative graph JSON.

The API is scoped to a small anonymous demo, not confidential multi-user research hosting. It has no authentication, per-user quotas or durable recovery. Adding such requirements needs a separate access/storage design.

## Deployment

`Dockerfile` builds the TypeScript frontend in Node 24, installs locked Python service dependencies into Python 3.13, and runs as a non-root user. PyTorch is absent. One web container serves both layers under the same origin.

`render.yaml` is a prepared Render Blueprint with manual deployment and one worker. Its Starter plan selection is configuration, not a purchased service. No hosting resources have been created. Before applying it, confirm account access and plan cost, use the tested commit, and run staging checks for HTTPS, complete upload/export, invalid inputs, cancellation, overload, expiry and restart behavior. Keep public deployment on hold until those checks pass.

Linux CI builds and runs the actual Docker image. The local Docker engine was stopped during development, so the container evidence must come from that CI run. Follow the status recorded in VERIFICATION.md rather than treating a Dockerfile as a successful deployment.

Primary deployment references: [FastAPI workers](https://fastapi.tiangolo.com/deployment/server-workers/), [Python process API](https://docs.python.org/3.13/library/multiprocessing.html), [Render Blueprint](https://render.com/docs/blueprint-spec).

## Reproducing performance evidence

Run `.venv/bin/python scripts/measure_service.py --output docs/performance.json`. The saved macOS probes run each case five times and include worker startup, refinement, independent replay and serialization. Observed completed medians were 0.20–0.31 seconds, with sampled RSS at most 40.42 MiB. The 1,024-node path was rejected at the trace budget with no ceiling.

These small probes do not establish production p95, maximum throughput or a hosting bill. RSS is sampled every 20ms and can miss a transient peak. Repeat on the target Linux instance and investigate difficult topologies before expanding limits.
