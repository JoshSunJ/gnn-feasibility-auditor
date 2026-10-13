# Operating the SWE application

## Architecture and job lifecycle

One Uvicorn API process serves the built React assets and HTTP endpoints. A supervisor thread admits a bounded queue and starts independent spawned Python workers. CPU work runs outside the request event loop. Each job uses an unguessable identifier and a private temporary directory.

`queued → running → completed | rejected | timed_out | cancelled | failed`

Only `completed` jobs expose artifacts. A worker loads the original JSON text with the strict core loader, checks input budgets, refines to stability, independently replays the certificate, serializes bounded artifacts, and then publishes completion. A refinement-budget exception never becomes a partial WL match or a training ceiling.

Cancellation terminates the worker and removes partial artifacts. Runtime and RSS watchdogs supervise execution; Linux workers also have an address-space limit. Admission is bounded across the whole single process. Multiple Uvicorn workers would create independent queues and violate the intended global capacity; use exactly one worker.

The HTTP server caps concurrent requests at 32 in Docker. At most two upload bodies are buffered concurrently, each with a 10-second read deadline and enforced byte limit; job capacity is checked before buffering. Artifacts stream in 64 KiB chunks from a file opened under the expiry lock. An already-open download may finish after TTL expiry; new requests receive 404. Job/upload overload returns 429 with Retry-After. Server connection overload can return 503. This anonymous service has no fairness guarantees or durable scheduler.

## API

| Endpoint | Behavior |
|---|---|
| `GET /api/health` | Readiness and active/queued counts; no dataset identifiers |
| `GET /api/config` | Public input/execution budgets and scope |
| `GET /api/demo` | Packaged synthetic fixture |
| `POST /api/jobs?mode=auto` | Original UTF-8 JSON body; Content-Type application/json; 202 admission; auto/trace/partition mode |
| `GET /api/jobs/{id}` | State, actual round or processed-splitter/color progress, completed summary or readable failure |
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
| Upload bytes | 16 MiB |
| Graphs / total nodes / total edges | 2,048 / 50,000 / 200,000 |
| Feature dimension | 64 |
| Cumulative node-round trace cells | 131,072 |
| Moved vertices recorded in compact split evidence | 500,000 |
| Total serialized artifacts | 64 MiB |
| Worker wall time / memory | 20 seconds / 256 MiB |
| Active workers / queued jobs | 1 / 3 |
| Retained jobs | 8 |
| Terminal-result retention | 15 minutes |

These are admission ceilings, not promises that every input below them completes. Difficult refinement or large artifacts can hit a later budget. Override through `AUDITOR_` plus the uppercase field name in `gnn_auditor/service/limits.py`. Validate changed settings with the capacity probe and failure suite; instance-level memory must cover the API plus all workers and downloads.

Automatic mode uses synchronous trace refinement for at most 512 total nodes; larger inputs use the compact partition engine. Both have independent verifiers. Explicit trace mode may hit its trace budget on a long path; automatic/compact mode avoids retaining all rounds. Progress counts are actual work, not completion percentages. v1 certificates contain rounds; v2 contain justified split events and final colors. Work telemetry is a producer measurement, not verified mathematical evidence.

The browser draws topology up to 500 nodes per graph. Larger graphs retain all audited inputs and have a node-ID search with up to 200 displayed options. Color histograms paginate 100 entries and classes paginate 20 entries, with search and conflict filtering. These display bounds never alter the audit. Compact inspection is labeled final-only; its single display snapshot is not a synchronous WL round. Full v2 evidence remains in the certificate download, with no duplicated event trace in the inspection payload.

## Privacy, expiry and restart

No accounts or persistent dataset history are implemented. Job URLs are bearer capabilities: anyone with a URL can inspect its result until expiry. No job list is exposed. Responses are not cached; the page sets no-referrer and same-origin framing policies. Inputs and results are temporary files and disappear on expiry or shutdown. A restart loses every job; clients receive an unavailable/expired/restarted message and must submit again.

Uvicorn access logging is disabled so capability URLs and dataset details do not enter request logs. Worker failures return fixed internal-error messages. No uploaded model files, executable files or pickles are accepted. Audit inputs are always numeric, declarative graph JSON.

The API is a bounded anonymous auditing tool. It has no authentication, per-user quotas or durable recovery. Confidential multi-user hosting needs a separate access/storage design.

## Deployment

`Dockerfile` builds the TypeScript frontend in Node 24, installs locked Python service dependencies into Python 3.13, and runs as a non-root user. PyTorch is absent. One web container serves both layers under the same origin.

The [hosted app](https://gnn-feasibility-auditor.onrender.com) runs a Docker web service on Render Free compute in Oregon, with one API process, one active audit worker and manual deployments. Repository access and hosting are connected; the repository remains private. Health checks use `/api/health`. The host overrides `AUDITOR_TIMEOUT_SECONDS=90`; memory remains 256 MiB per worker and retention remains 900 seconds. The library/service local default remains 20 seconds. No paid compute was purchased.

The original 20-second host budget timed out on both real inputs and the 50,000-node path without publishing a ceiling. All three completed under the measured 90-second budget and their downloaded certificates independently replayed. Hosted queue overload returned 429; all four disposable queued/running jobs were cancelled with no artifact/ceiling. Actual 15-minute expiry and redeployment invalidation were checked. [docs/hosted-verification.json](docs/hosted-verification.json) records the tested commit and observations. Repeat the appropriate hosted smoke checks before promoting a code/runtime change; prior observations are not evidence for an untested commit.

Render describes Free services as previews/hobby services, with idle spin-down after 15 minutes and filesystem loss on restart/spin-down. A resume demonstration can use that plan with explicit cold-start and expiry expectations; it is not an always-on production SLA. Bandwidth/build allowances and spend settings are workspace-dependent. See [Render Free limitations](https://render.com/docs/free). Paid compute is a separate budget decision if an always-on service becomes necessary.

Linux CI builds and runs the actual Docker image. The local Docker engine was stopped during development, so the container evidence must come from that CI run. Follow the status recorded in VERIFICATION.md rather than treating a Dockerfile as a successful deployment.

Primary deployment references: [FastAPI workers](https://fastapi.tiangolo.com/deployment/server-workers/), [Python process API](https://docs.python.org/3.13/library/multiprocessing.html), [Render Blueprint](https://render.com/docs/blueprint-spec).

## Reproducing performance evidence

`docs/performance.json` preserves the original v0.2 small-prototype probes. For current automatic/compact mode run `.venv/bin/python scripts/measure_scale_service.py --root /tmp/gnn-tu-data`, after regenerating the training inputs with `scripts/real_data_study.py`. Use separate lightweight service and ML environments so serving-worker RSS does not include PyTorch.

Current macOS probes use three repetitions, including startup, refinement, independent replay, serialization of four artifacts and streamed reads. 50,000-node paths, cycles and uniquely featured paths completed, as did PROTEINS and ENZYMES training inputs. Completed medians for those larger cases were 1.15–3.00 seconds and maximum sampled worker RSS was 210.28 MiB. An explicitly requested 1,024-node full trace was rejected with no ceiling. Complete records are in `docs/scale-service-performance.json` and actual-input provenance in `docs/real-data-study.json`.

These small probes do not establish production p95, maximum throughput or a hosting bill. RSS is sampled every 20ms and can miss a transient peak. Repeat on the target Linux instance and investigate difficult topologies before expanding limits.
