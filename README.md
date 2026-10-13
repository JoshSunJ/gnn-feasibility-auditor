# GNN Feasibility Auditor

A research-first auditing library and full-stack application for graph-level classification. It audits the **actual node features** using exact joint 1-WL color refinement, finds indistinguishable graphs with conflicting training labels, and computes the resulting training-accuracy upper bound.

The core needs only Python 3.10+. The service uses Python 3.13, FastAPI and supervised worker processes; the interface uses React, TypeScript and Cytoscape.js. Benchmarks and the PyTorch Geometric adapter are optional. Independently verified reports can also be exported as self-contained offline HTML.

Private project: [repository](https://github.com/JoshSunJ/gnn-feasibility-auditor), [release tracker](https://github.com/JoshSunJ/gnn-feasibility-auditor/issues/1), [release checks](https://github.com/JoshSunJ/gnn-feasibility-auditor/actions). Public hosting remains on hold until release/staging gates pass. The application has no real-data ML study yet; saved model fits use the synthetic correctness fixture.

Read [RESEARCH.md](RESEARCH.md) for the mathematical claim, assumptions, data format, proof sketch, primary references and correctness criteria. Read [VERIFICATION.md](VERIFICATION.md) for the acceptance gate and measured results. The core passed before benchmarks or the interface were implemented.

## Start here

For the complete upload-to-report application, use Python 3.13 and Node 24:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.lock
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python -m uvicorn gnn_auditor.service.app:app --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 32 --no-access-log
```

Open **http://127.0.0.1:8000**, select **Load demo** or choose a supported training JSON file, then **Run exact audit**. The interface shows real job state, cancellation, verified results, graph comparison by refinement round, actual-feature inspection and exact downloads. Changing the input clears previous results. API documentation is at `/docs`.

For frontend development, run `npm --prefix frontend run dev` alongside the Python service; Vite proxies `/api` to port 8000. For a Docker deployment, run `docker build -t gnn-auditor .` and `docker run --rm -p 8000:8000 gnn-auditor`. See [OPERATIONS.md](OPERATIONS.md) for execution budgets, temporary-data behavior and deployment instructions.

For an offline demonstration requiring no server, open **[index.html](index.html)** at the project root. This is a saved five-graph report, separate from the live application. Choose a WL class, choose Graph A and Graph B, move the refinement slider, and select nodes to inspect their actual input features. The default comparison is the six-cycle versus two disconnected triangles.

`gnn_auditor/explorer.html` is the source template and has no embedded dataset. Opening it directly now shows an explanation and a link to the working demo, instead of empty graph selectors. `examples/explorer.html` is also a generated, usable report.

The live interface accepts training JSON; the offline report only inspects its embedded inputs. You can also audit data with the CLI and generate an offline report. [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) records implementation status; [SHIPPING_PLAN.md](SHIPPING_PLAN.md) preserves the product direction and release gates.

## Engineering structure

```text
gnn_auditor/            exact core, independent verifier, CLI and optional ML tools
gnn_auditor/service/    HTTP contracts, admission queue, isolated workers and budgets
frontend/src/          React/TypeScript upload, job state and Cytoscape comparison
frontend/e2e/          desktop/mobile Playwright workflows used in Linux CI
tests/                 independent oracle, generated properties, service failures, adapters
scripts/               container smoke test and reproducible capacity probes
.github/workflows/     core, service/browser, optional ML and Linux Docker checks
```

The same Python engine serves notebooks, CLI and HTTP jobs. The browser displays verified evidence rather than implementing WL again. A worker publishes artifacts only after refinement stabilizes and independent certificate replay succeeds. Interrupted jobs never expose a ceiling. See [OPERATIONS.md](OPERATIONS.md) for the lifecycle and tradeoffs.

## Optional PyTorch Geometric ingestion

Install `.[pyg]` in a separate ML environment. Accept in-memory `Data` objects after the actual model preprocessing:

```python
from gnn_auditor.pyg import dataset_from_pyg, audit_pyg

report = audit_pyg(graphs, train_indices=[0, 3, 8], include_certificate=True)
```

The adapter preserves `x`, dtype, dimension, integer graph labels, isolated nodes and explicit training selection. It accepts exactly one reciprocal COO entry per direction for each simple undirected edge. Extra fields such as `edge_attr`, `pos`, `batch` and weights, missing features, self-loops, parallel edges and mixed precision are rejected. It does not load uploaded pickles or infer replacement features. `dataset_from_pyg` returns the same `Dataset` used by the CLI; use `dataset_object` to export its represented inputs.

## Release validation

```sh
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
```

Service/test dependencies are locked in `requirements-test.lock`; frontend versions and transitive resolution are in `frontend/package-lock.json`. Optional ML dependencies stay out of the serving image. Linux CI additionally runs real desktop/mobile browser workflows, wheel/CLI checks and a Docker HTTP smoke test. See [VERIFICATION.md](VERIFICATION.md) for observed results and [docs/performance.json](docs/performance.json) for measured synthetic probes; these are not production p95 or real-data ML benchmarks.

## Run from this directory

No installation is required:

```sh
python3 -m gnn_auditor audit examples/conflicts.json
python3 -m gnn_auditor audit examples/conflicts.json --format json --certificate --output audit.json
python3 -m gnn_auditor verify examples/conflicts.json audit.json
python3 -m unittest discover -s tests -v
```

The sample produces a ceiling of **4/5 = 80%**, one unavoidable training error, and two cross-label witness pairs. The cycle, its duplicate and two triangles form a single class with label counts `connected: 2`, `disconnected: 1`. The path and feature-marked triangles are separate classes. This is a **synthetic correctness fixture**, not a real-world dataset or generalization experiment.

`--max-pairs N` controls how many concrete cross-label pairs appear (default 20). All equivalence classes and their complete memberships and label counts are always included. The report states the exact number of omitted witnesses. `--certificate` requires JSON and includes the full trace for independent replay.

To get an installed `gnn-audit` command, optionally use `python3 -m pip install .` in a virtual environment. This works without importing PyTorch into the core.

## Supply your training graphs

Export only training samples, after the model's actual feature preprocessing, using the JSON contract in RESEARCH.md and [examples/conflicts.json](examples/conflicts.json). Required top-level fields are `schema_version: 1`, `split: train`, `graph_type: simple_undirected`, `feature_dtype: float32` or `float64`, `feature_dim`, and `graphs`.

Every graph has a unique string ID, a string or integer label, explicit nodes with IDs and numeric feature vectors, and unordered edges given as endpoint pairs. IDs are bookkeeping and never become initial colors. Isolated and empty graphs are supported. `feature_dim: 0` explicitly supports zero-dimensional vectors; every node must still supply `features: []`.

Missing features, unsupported attributes, directed/multiple/self edges, duplicate IDs/keys/edges, unknown endpoints, nonfinite values, dimension mismatches and non-training files are rejected with an error and exit status 2. Class membership includes duplicate samples; the bound uses unweighted micro accuracy.

Equality means exact equality of the declared represented IEEE values, with signed zero normalized. JSON numeric values are parsed into Python binary64 values, then converted once to binary32 if declared. Use a round-trip export of the actual model tensor values in its precision. Close values are never grouped using a tolerance. A model with extra positional, random, edge, graph-level or higher-order inputs needs an audit that includes those inputs; this prototype does not cover them.

## Exact refinement and independent replay

All graphs are refined on their disjoint union using a common palette. Each signature retains the old color and the full neighbor-color multiset, including multiplicities. Interning uses complete tuple equality. Dictionary hashes are only lookup accelerators; equal hashes never determine equivalence. No graph digest is computed or accepted as proof.

Refinement runs until a round creates no additional color classes. There is no round cap that could turn a temporary match into a claimed impossibility. Stable color histograms identify 1-WL equivalence, which does not establish isomorphism. Palette IDs are local to the report; do not compare IDs from different reports.

For equivalence classes C with label counts n(C,y), the ceiling is

    U = sum_C max_y n(C,y) / N.

The independent verifier replays exact signatures from the input topology and features and checks stability, membership, arithmetic and witnesses. It does not call the refinement engine. The test oracle separately compares pairs using expanded multisets, linear equality searches and a safe fixed number of rounds.

## Optional model benchmarks

Use a virtual environment with a Python release supported by your PyTorch version. The recorded run used Python 3.13.13, PyTorch 2.14.1 and NumPy 2.5.4 on macOS arm64; the actual report carries the environment returned at execution time.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install '.[benchmark]'
.venv/bin/python -m gnn_auditor benchmark examples/conflicts.json --epochs 300 --seeds 0 1 2 --output benchmarks.json
.venv/bin/python -m unittest discover -s tests -v
```

The models are small trainable GIN and symmetrically normalized GCN implementations. They use the supplied features, a shared input projection, three message-passing layers by default, concatenated per-layer sum pooling, and a classification head. There are no generated node features, dropout or batch normalization. Training uses full-batch Adam on CPU with the declared feature dtype. Every run first produces and independently verifies a core certificate.

Reports contain all settings, label predictions, logits, sampled training histories, final and best observed training fits, and within-class numerical diagnostics. “Best observed” is measured on these training examples at every epoch, including initialization; it is not model selection on held-out data. Dense adjacency is deliberately limited to 512 nodes per graph and 2,000,000 total adjacency entries.

The saved six runs in [examples/benchmarks.json](examples/benchmarks.json) all achieved a final 80% training fit. Their maximum within-class logit difference was exactly 0 in these measurements. This demonstrates the fixture, not a guarantee for future training. Stochastic/context-dependent evaluation and floating-point artifacts are outside the exact mathematical claim; numerical anomalies are surfaced, not used to certify the bound.

`requirements-benchmark-tested.txt` records the exact installed dependency versions for reproducing this environment. Use it instead of the unpinned benchmark extra when those versions are compatible with your Python and platform.

## Visual interface

Open [index.html](index.html) or [examples/explorer.html](examples/explorer.html) in a browser. Both include the demonstration and saved benchmarks. To build an explorer for your own training data:

```sh
python3 -m gnn_auditor explore training.json --output explorer.html
python3 -m gnn_auditor explore training.json --benchmark benchmarks.json --output explorer.html
```

`explore` independently replays a certificate before exporting. Benchmark attachments must match the complete represented input dataset, rather than a matching hash or accuracy value. Select a WL class or any two graphs, move through refinement rounds, and select nodes to inspect their real feature vectors and exact signatures. Color IDs and histogram counts accompany color to make comparisons explicit. Graph layout coordinates are display-only. The interface exports input graphs and the certificate as JSON.

The explorer is an inspection interface, not an in-browser implementation of WL. Reaudit changed inputs with the CLI. No network service, upload or hosted deployment is needed. Labels and identifiers are rendered as text, and embedded JSON is escaped so untrusted dataset strings cannot create executable markup.

The export dialog shows exact JSON with Download and Select controls. Some embedded browsers do not expose download events; copying the displayed JSON or writing reports with the CLI provides the same exact certificate. Large integer labels are preserved as exact text rather than rounded by JavaScript.

## Limits and next steps

The result bounds **training accuracy for this exact training multiset** under the stated model assumptions. It does **not predict test accuracy**. The ceiling can be loose for a particular GNN or shallow depth. A 100% ceiling only means this audit found no forced cross-label conflicts. Unique continuous features frequently make the ceiling uninformative; the auditor does not silently quantize them to manufacture collisions.

This small prototype stores full per-round traces and sorts exact signatures. Worst-case refinement can take a linear number of rounds in the total node count; trace memory can therefore grow substantially. Use modest datasets. A production extension could use partition-refinement algorithms and stream certificates while retaining exact equality. Directed/attributed graphs, dataset-specific ingestion adapters, weighted/multilabel losses, and preprocessing manifests would require separate contracts and tests.

## Files

- `gnn_auditor/data.py`: strict graph ingestion and represented-feature equality.
- `gnn_auditor/refinement.py`: exact joint 1-WL to stability.
- `gnn_auditor/report.py`: class label counts, ceiling and witnesses.
- `gnn_auditor/verify.py`: independent certificate replay.
- `gnn_auditor/cli.py`: audit, verify, benchmark and explore commands.
- `gnn_auditor/benchmark.py`: optional trainable GIN/GCN experiments.
- `gnn_auditor/explorer.py`, `explorer.html`: verified local report interface.
- `tests/`: independent reference, adversarial core and integration checks.
- `examples/`: actual synthetic inputs, text/JSON audit, measured benchmarks and explorer.
