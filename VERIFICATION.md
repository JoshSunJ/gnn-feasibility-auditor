# Verification record

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
