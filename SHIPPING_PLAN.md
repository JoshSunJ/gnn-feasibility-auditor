# Product direction and shipping decision

Current follow-up, 2026-10-12: v0.3 adds the exact compact engine and independent split verifier, actual-feature PROTEINS/ENZYMES training-input studies, measured 50,000-node service probes and large-data inspection. The user has authorized live deployment. Remaining gates are the current extension's Linux/browser CI, installation/connection of Render with private-repository access, and actual hosted checks. render.yaml now defaults to Free/manual deployment; paid hosting and making the repository public remain separate decisions. The original plan below is historical; refer to RELEASE_CHECKLIST.md and VERIFICATION.md for current status.

Update on 2026-10-12: the SWE release branch now implements the upload/API workflow, React/TypeScript/Cytoscape interface, bounded jobs, optional PyG adapter, failure tests and delivery configuration. See RELEASE_CHECKLIST.md, OPERATIONS.md and VERIFICATION.md for current evidence. The original plan below is retained as design context; its missing-work table describes the initial prototype, not the current implementation. Real-data studies and hosted staging remain outstanding.

Decision on 2026-10-10: **hold public deployment**. The exact auditing core is verified and usable locally. The application is a report prototype, not yet a public upload-and-audit service. The corrected root `index.html` is the intended local entry point.

## What the tool should help someone do

Before training a graph classifier, inspect whether the supplied training inputs force label contradictions for a message-passing model. Export a reproducible, independently checkable report showing the unavoidable errors and the actual conflicting graphs. A ceiling of 100% remains an inconclusive audit result, not a promise of successful fitting.

The useful workflow is: choose a demo or upload training JSON → confirm inputs and scope → run exact audit → inspect conflicting classes → export inputs, certificate and results. A researcher should also be able to call the same library from a training notebook.

## Current readiness evidence

| Area | Current evidence | Missing for release |
|---|---|---|
| Mathematical core | Exact feature-aware joint 1-WL, majority ceiling, independent replay; 25 automated tests; agreement on 5,265 oracle pairs | Broader generated/property tests and versioned public API |
| Inputs | Strict JSON, explicit precision and dimensions, training-only contract | A PyTorch Geometric adapter, preprocessing manifest, useful browser validation messages |
| Interface | Generated report, class/pair/round/node inspection, export dialog | New-data upload, job/error/cancel states, automated browser regression tests |
| ML evidence | Six synthetic GIN/GCN fits reproduce the 80% fixture ceiling | Real dataset studies with original features, fixed training splits and preprocessing recorded |
| Performance | Small correctness fixtures; full traces retained in memory | Time/RSS measurements across graph sizes and difficult refinements; measured capacity limits |
| Hosting | No public service exists | Bounded execution, input/report quotas, tested failure handling, CI, container smoke test |

Passing the mathematical tests does not establish safe or usable hosting behavior.

## Features to implement in order

### 1. Actual-input ingestion and guided audit

Add `audit_pyg(graphs, train_indices=...)` and an export adapter taking in-memory PyTorch Geometric `Data` objects. Preserve `x` and its supported precision, graph labels, isolated nodes and the explicit training sample list. PyG stores `x`, `edge_index`, `edge_attr`, and other fields separately; the adapter must account for every model-relevant input. See [PyG Data documentation](https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.data.Data.html).

Reject missing `x` and unsupported inputs; do not silently insert constants, remove edge attributes, or substitute degrees. Undirected COO often lists both directions: the adapter must validate reciprocity and actual simple-graph semantics before mapping it to one unordered edge. It must not mistake parallel edges for harmless duplicates. Test node/graph permutations and adapter export versus directly constructed JSON.

In the UI, accept JSON text or files, show useful field locations for errors, and explicitly show what the model consumes. Send original JSON text to Python rather than parsing and reserializing it through JavaScript; large integer labels and duplicate-key detection must survive. The core loader remains the authority; API frameworks must not coerce unsupported inputs into accepted values.

**Value:** researchers can use the tool with their training pipeline instead of manually constructing a demo file. SWE evidence: a typed API and complete user workflow. ML evidence: correct accounting of actual inputs.

### 2. Reproducible studies and conflict diagnosis

Evaluate at least two real datasets with fixed training selections, original node features, exact declared precision, and an explicit preprocessing manifest. Audit source labels and license before redistribution. Do not claim a real dataset has collisions until measured. If original continuous features produce a 100% ceiling, report that result honestly.

For a modest number of witness pairs, add a separately bounded, exact feature-preserving isomorphism check. Report either duplicate/isomorphic inputs with contradictory labels, non-isomorphic graphs that 1-WL cannot distinguish, or an unfinished isomorphism check. This extra diagnosis must not change the certified WL result. Isomorphism checking can be expensive, so do not run it indiscriminately on all pairs.

Save seeds, model settings, training indices, actual features, logs, final training fit and gap to the ceiling. Keep GIN and GCN as baselines. Add a feature-only pooled classifier to identify when topology contributes little. A content checksum may identify an experiment artifact; it must never replace exact equality as proof of WL equivalence.

**Value:** the tool answers whether to investigate conflicting labels or model expressivity. Resume evidence should describe measured datasets and reproducibility, not only a toy graph picture or an assumed accuracy improvement.

### 3. Edge-aware and directed input contracts

Add an explicitly versioned extension for edge-feature-aware refinement and separate incoming/outgoing neighborhoods. Preserve multiplicities and complete tuples. Expand the proof, certificate replay and oracle tests before accepting these inputs. Molecular datasets commonly use bond attributes; stripping them would audit a different model input. This feature becomes a release prerequisite if the launch promises to support such datasets.

**Value:** broadens the set of legitimate graph learning tasks. The v1 public scope may stay simple undirected and reject these cases clearly until the extension is verified.

### 4. Bounded jobs, performance and release automation

Move audits to killable worker processes with a bounded admission queue. Provide queued, running, completed, rejected, timed-out, cancelled and failed states. Publish actual refinement-round/color counts, not an invented completion percentage. Enforce byte, graph, node, edge, feature-dimension, output, runtime and memory budgets before/while processing.

Timeout/cancellation/resource exhaustion must return **incomplete, no certified ceiling**. Never accept a capped refinement match as stable equivalence. Cap active jobs; reject overload cleanly; expire temporary reports. Never accept uploaded pickles or executable model files. Keep dataset contents out of logs.

Measure audit and independent-verification time, peak resident memory, report size, and scaling versus topology, node count, feature diversity and the number of refinement rounds. Reduce trace memory with a separate verified summary/streaming mode if measurements require it. Do not choose public capacity limits from the six-node fixture.

Add CI for the core, optional benchmarks, packaged CLI, certificate replay, property tests, and browser workflows. Build and smoke-test the Linux container; the existing benchmark measurements were made on macOS, so Linux validation remains necessary.

**Value:** a reliable service with demonstrable engineering tradeoffs and measured operating limits.

## Chosen technology stack

| Layer | Choice | Reason |
|---|---|---|
| Core | Python 3.13 package; retain the exact engine and independent verifier | Keeps one mathematical implementation usable from CLI, notebooks and service |
| HTTP API | FastAPI + Pydantic for response/job contracts; strict core loader for raw dataset inputs | Integrates directly with Python; useful documented interfaces; prevents a second JavaScript refinement implementation |
| UI | React + TypeScript + Vite | Suits upload/job/inspection states and testable components; this application does not need server-side rendering |
| Graph view | Cytoscape.js | Graph-specific layout, selection, pan and zoom; share exact palette IDs with labels rather than depending on color alone |
| ML experiments | PyTorch; optional PyTorch Geometric adapter | Matches the models and inputs researchers already use; keep training dependencies out of the serving image |
| Tests | Keep current unittest suite; add pytest/Hypothesis and Playwright as coverage demands | Independent mathematical oracle, generated invariants and complete browser workflows verify different failure modes |
| Delivery | Docker + GitHub Actions | Reproducible Python runtime, frontend build, Linux checks, gated releases |

FastAPI supports container deployment and static-file serving, Vite supports the React/TypeScript application build, and Cytoscape.js provides graph interaction/layout APIs. These choices are engineering judgments for this application, not claims that one framework is universally superior. Primary documentation: [FastAPI Docker](https://fastapi.tiangolo.com/deployment/docker/), [Vite](https://vite.dev/guide/), [Cytoscape.js](https://js.cytoscape.org/), [GitHub Actions Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).

## Chosen deployment stack for the first public version

Use **one CPU Docker web service on Render**, serving the built React assets and FastAPI under the same origin. Run one API process with a small, bounded set of killable audit child processes. Avoid a second hosting platform and cross-origin configuration for the initial app. Render supports Docker services, Git-backed deployments, health checks and managed HTTPS; see [Docker deployment](https://render.com/docs/docker) and [web services](https://render.com/docs/web-services).

Initial scope: small anonymous audit sessions; no accounts, persistent dataset history, or public arbitrary model training. Offer downloadable reports; keep uploaded inputs/results temporary with explicit expiry. State loss on restart must be communicated as expired/interrupted work rather than a successful audit. Render's filesystem is ephemeral unless a persistent disk is configured: [disk documentation](https://render.com/docs/disks). Process supervision, TTL cleanup and restart behavior must be implemented and tested before release.

Select the instance size and operating budgets only after Linux load tests. Do not infer a hosting bill from an untested job workload. Bind to Render's supplied port; add readiness/liveness checks, bounded structured logs and graceful shutdown. Use a deployment definition in the repository and pinned dependencies once this service is implemented.

Serve saved benchmark studies and run reproducible training locally or in CI. If real usage later needs concurrent long-running training, durable queues or multi-instance audits, move compute to a dedicated worker service with an external queue. Render has [background worker services](https://render.com/docs/background-workers). Durable history is a later product requirement, not a reason to add storage services before the first useful audit workflow.

## Public-release gates

1. A first-time user can load a demo and upload valid supported training JSON, obtain a completed verified result, inspect its actual conflicting graphs, and export/replay it without editing code.
2. Bad files, missing/unsupported features, duplicate JSON keys and oversized inputs produce understandable errors. Wrong template entry has a recovery path. No empty unexplained selectors.
3. Every completed audit agrees with the CLI and independently replays. Interrupted or resource-limited jobs never display a certified ceiling.
4. Real dataset experiments are reproducible with recorded original features, preprocessing and training selection. Scope exclusions remain prominent.
5. Linux performance/overload/restart/cancellation tests establish the service's published limits. Dataset contents do not enter logs and temporary data expires as documented.
6. CI, packaging, browser and container smoke checks pass. External staging checks confirm health endpoints, HTTPS behavior and the complete upload-to-export workflow.

The next implementation milestone is the PyG adapter and a locally tested upload/API workflow. Deployment should wait for the relevant gates; no hosting resources were created for this plan.

## Resume evidence to collect

- Number and size of real datasets actually audited; conflicting classes and unavoidable training errors found, including any legitimate 100% ceilings.
- Exactness validation: independent oracle pairs, property cases, certificate replay and adversarial collisions.
- Median/p95 runtime, peak memory and throughput at the published input limits, including failed and cancelled jobs.
- Reproducible GIN/GCN fits and the training gap to the certified ceiling; no claims that the ceiling predicts held-out accuracy.
- End-to-end shipping evidence: documented API, browser tests, Docker/CI, deployment health and failure handling.

Describe completed work as completed and roadmap work as planned. The mathematically meaningful result and a usable, reliable workflow are stronger evidence than a long list of unrelated technologies.
