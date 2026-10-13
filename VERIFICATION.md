# Verification record

## Current compact-engine extension (v0.3, 2026-10-12)

Research/design was recorded first in SCALE_RESEARCH.md. The compact producer agrees with the independent pairwise oracle on all 5,265 existing pairs. Its separate verifier reconstructs the actual-feature partition, replays only forced count-group splits and checks final equitability; it does not call the producer. Tampering, omitted/duplicate groups, early stops and arbitrary individualization fail. Full synchronous trace mode remains available.

Local combined environment: **51 Python tests passed without skips**, including compact proof/export checks and 14 service tests. **Eight frontend tests** and the TypeScript/Vite production build passed. New checks cover mode selection, actual opposing labels, class filtering/pagination, bounded node search/histogram rendering and large-integer label preservation. CI for this extension is pending; the historical v0.2 Linux results below do not establish v0.3 Linux or hosted success.

Real training-input audits: PROTEINS (890 graphs, 34,099 nodes, 4 actual float32 features) and ENZYMES (480 graphs, 15,480 nodes, 21 features). Both independently replayed and returned 100% ceilings with zero forced errors. No held-out inputs were audited. These studies preserve the recorded PyG loader's continuous attributes, one-hot supplied node labels and topology; default loader removal/coalescing is recorded before model consumption. Aggregate results, selection indices, loader settings and source-file digests are in docs/real-data-study.json. Digests are provenance only, never equivalence proof. No real-data model training was performed.

Isolated service measurements: three repetitions each on 512/6,000/50,000-node paths, 50,000-node cycles, 50,000-node uniquely featured paths and both real inputs. All compact jobs completed, including independent replay and four artifacts. Larger completed medians were 1.15–3.00 seconds; maximum sampled worker RSS was 210.28 MiB. Explicit full trace on a 1,024-node path was rejected at the trace budget, with no ceiling. See docs/scale-service-performance.json. The original exporter initially exceeded memory on the 50,000-node path; duplicate viewer evidence and pretty-printed copies were removed before the saved final measurements. RSS is sampled; these macOS measurements are not production p95, throughput or target-host capacity evidence.

Public service state: **not deployed**. Render was discovered and suggested but its integration is not yet installed/connected. The Free/manual Blueprint is prepared; no paid resources or public repository change have been made. Hosted HTTPS, expiry/restart and complete workflow checks still require access. Deployment remains an open step, not a claimed achievement.

Core acceptance gate passed on 2026-10-10, before implementing model benchmarks or the visual interface.

- Python 3.14.7; dependency-free standard-library test runner.
- All 18 core tests passed (`python3 -m unittest discover -s tests -v`).
- All 2,850 pairs among the 76 simple labeled-by-node-order graph representations through four vertices agree with a separate pairwise WL oracle. These include isomorphic representations; they are not 76 distinct isomorphism classes.
- All 2,415 pairs among 70 seeded feature-labeled random/repeated graphs agree with that oracle.
- The oracle uses linear equality searches, expanded neighbor multisets, and a fixed safe iteration count. It does not use production interning, joint dataset refinement, compressed multiplicities, or the production stopping criterion.
- Covered late separation, ordering/ID invariance, exact adjacent float values, float32 conversion, signed zero, missing/nonfinite features, multiplicities, zero-dimensional vectors, empty graphs, typed/multiclass labels, brute-force majority optimality, and deliberately colliding intern-table hashes.
- Independently replayed the exported example certificate against the original graph file. Replay checks exact signatures, injective palettes, every node/color assignment, stable partition, class memberships, label counts, bound arithmetic, and each reported witness. Tampered traces, counts, classes, feature colors and witness labels are rejected. Consistent palette remapping is accepted.
- End-to-end JSON audit, certificate verification, text report and invalid-input exit behavior passed.

The synthetic example has five training samples and three stable WL classes. The six-cycle, its duplicate, and two triangles form one class, with labels `connected: 2` and `disconnected: 1`. The path and feature-marked triangles form separate classes. Therefore at most 4/5 = 80% of these training labels can be fitted by a classifier in the stated scope; at least one training error is unavoidable. There are two concrete cross-label witness pairs.

These tests check implementation correctness, not the validity of unspecified model inputs or predictive performance on a test set. See RESEARCH.md for the proof and assumptions. Later integration checks and benchmark measurements will be recorded below.

## Integration and measured benchmarks

After the core gate, all 25 tests passed with the optional PyTorch environment, including reproducible CPU training, exact float32 input conversion, empty/zero-dimensional inputs, actual-input benchmark attachment checks, verified explorer export, escaping of untrusted strings, and exact preservation of large integer labels in display/export text. The default Python environment runs 22 tests and skips the three optional model tests.

Six trainable model runs on the synthetic fixture: GIN and GCN, each with seeds 0, 1 and 2; 300 epochs, 32 hidden units, three layers, full-batch Adam at learning rate 0.01, CPU float64, no dropout or extra node features. Each run had final and best observed training accuracy 4/5 = 80%, maximum within-class logit difference 0, and no differing within-class predictions or observed accuracy above the ceiling. Full settings, runtime versions, actual input dataset, histories and logits are saved in examples/benchmarks.json.

The visual interface was checked in the local browser: displayed ceiling and conflicts, default cycle/triangles comparison, switching to the path, stable-round colors and exact histograms, actual-feature/signature node inspection, and measured benchmark rows. At a 390px viewport the graph panels stack and the page has no horizontal overflow (document width = viewport width = 390px). The exact JSON export dialog, parsed certificate contents and close control were checked; the browser reported no warning/error logs. The embedded browser did not report a download event, so automatic download completion is unverified there; exact JSON remains visible/selectable and CLI output is independently verified.

Packaging: built the Python wheel without runtime dependencies, installed it into an isolated target, and imported it outside the source checkout with the default Python environment. The installed package reproduced the 4/5 ceiling, passed independent certificate replay, and generated the visual interface using its bundled HTML template.

## Entry-point correction and release assessment

The user opened `gnn_auditor/explorer.html` directly and saw empty graph selectors. That file is the source template, with no attached dataset. It now displays an explicit explanation and a link to the generated demo instead of a blank report. A root `index.html` provides the intended local entry point; README.md explains this distinction and the CLI workflow for new graphs.

Browser regression check over localhost: the template showed the recovery message; its link opened the root demo; both graph selectors offered all five supplied graphs. Selecting the path and the stable round displayed distinct color histograms, and returning to the two triangles displayed matching histograms with conflicting labels. No warning/error logs were reported. All 25 automated tests passed again after the correction.

Public deployment remains on hold. SHIPPING_PLAN.md records the chosen stack, ordered feature work, and release gates. Real-data evaluation, a browser upload/API workflow, measured resource budgets, Linux hosting checks and release automation are still outstanding. No public hosting resources were created.

## SWE implementation on 2026-10-12

The earlier missing-work statement describes the initial prototype. The SWE release now implements a FastAPI service, spawned audit workers, streamed upload limits, bounded queue/retention, cancellation, timeout/RSS/Linux address-space limits, trace/output budgets, independent replay before publication and temporary-result expiry. No incomplete job exposes artifacts or a ceiling. A React/TypeScript/Cytoscape interface accepts original JSON text, follows job state, compares exact evidence and displays actual node features. Changing input clears previous results. Numeric label display uses exact parallel strings; downloads remain the server's original JSON bytes.

The optional PyG adapter preserves actual supported tensor values, precision, dimensions, integer labels, isolated nodes and explicit training selection. It validates reciprocal simple COO edges and rejects extra fields, missing features, nonreciprocal/parallel/self edges and mixed precision. It does not load executable or pickle data.

Local combined Python test environment: all 39 tests passed with no skips before the additional API-reference contract check. This includes the existing 5,265 oracle pairs, 60 deterministic generated permutation cases, benchmark and PyG checks, and nine real-worker service/failure tests. Final suite results are recorded below after the API-reference check. Frontend: four Vitest component tests pass; TypeScript checking and Vite production build pass. The initial UI bundle is approximately 231 kB minified; the roughly 441 kB graph viewer is loaded only after a completed audit.

Local browser checks: loaded demo, ran verified 4/5 audit, selected path versus cycle, selected the stable round and a node, inspected actual `[1]` features and complete signature, loaded a real JSON file, edited inputs (clearing results), and rejected duplicate JSON keys without showing stale results. At 390px, document and viewport widths were both 390px; graphs stack. No warning/error logs were reported for the checked flows.

Capacity probes: five repetitions each of a 128-node path, 512/2,048-node cycles, a 512-node uniquely featured path and a 1,024-node long-refining path. Completed medians were 0.20–0.31s with maximum sampled RSS 40.42 MiB. The last case was rejected at the trace budget and published no ceiling. Full environment/settings/observations are in docs/performance.json. These synthetic measurements do not establish production p95, throughput or real-data ML performance.

Initial Linux CI run 38326381724 passed Python 3.10/3.13 core/installed CLI checks, optional PyTorch/PyG checks and the actual non-root Docker HTTP smoke test. The browser job exposed an ambiguous test text selector matching both the node inspector and uploaded JSON. The selector was corrected to assert the exact visible feature value, and the suite was rerun. A successful Docker run verifies container packaging; it does not verify Render staging or public deployment. Those remain held.

Final local combined suite: **40 Python tests passed with no skips**, including the API-reference request-body contract and separate documentation-viewer policy. Four frontend component tests pass. Linux CI run [38326696243](https://github.com/JoshSunJ/gnn-feasibility-auditor/actions/runs/38326696243) passed all five jobs: core 3.10, core 3.13, service/browser, optional ML, and Docker. Its browser job passed all four desktop/mobile workflows, including actual native certificate downloads, file upload, node inspection, stable-round comparison and invalid-input clearing. Screenshots downloaded from its artifact are in docs/screenshots. Final release run [38326960609](https://github.com/JoshSunJ/gnn-feasibility-auditor/actions/runs/38326960609) passed all five jobs for `ca1deed`, including the API-reference update. PR #2 was merged as `5fa4932` after these checks passed. The final API reference was also visibly checked in the local browser.
