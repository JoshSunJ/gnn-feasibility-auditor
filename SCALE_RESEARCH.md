# Exact auditing beyond the small tracing prototype

Research/design gate recorded before implementation on 2026-10-12.

## Claim retained

The coarsest equitable partition refining the exact actual-feature partition on the disjoint union is the stable 1-WL partition. Equal final per-graph color multiplicities therefore force equal graph predictions for the supported deterministic shared message-passing/invariant-readout model class. Label majority counts give the same training micro-accuracy upper bound as the synchronous engine. This is neither graph-isomorphism certification nor test-accuracy prediction.

## Proposed summary engine

Maintain vertex sets (cells), a vertex-to-cell map, and a worklist of splitter cells. Count each vertex's neighbors in a splitter and split affected cells by those counts. Retain the largest child under its old cell ID and enqueue the other children; if the old cell was already queued, its retained child stays queued. Exact integers and full feature equality determine all decisions. Color IDs remain local.

This follows the established smaller-half partition-refinement approach. Primary reference: [Berkholz, Bonsma and Grohe](https://arxiv.org/abs/1509.08251). The implementation must be measured; the paper's complexity bound is not automatically a proven bound for this Python code.

The existing synchronous trace engine remains available for teaching/round inspection. A summary-engine certificate must identify its different method/version explicitly. Worklist splits must never be mislabeled as synchronous WL rounds.

## Compact certificate and independent proof check

The verifier reconstructs initial cells from exact represented features. Each event identifies the splitter in the current partition and lists moved groups from affected cells; the retained group is implicit. Every moved group must be justified by exact neighbor counts into that splitter, cover a whole count group, and be disjoint from the retained group. Cell IDs are allocated consecutively and no vertex is invented or duplicated.

Each legal split is forced by 1-WL: vertices with different counts into an already justified cell cannot stay equivalent. Thus the partition never refines beyond the stable WL partition. The verifier finally checks full equitability by comparing complete neighbor-cell multisets within every final cell. Any equitable refinement of the feature partition refines the coarsest equitable partition. These two directions establish equality to stable 1-WL. An unfinished or tampered split sequence fails verification.

The verifier must reconstruct events independently rather than call the producer. It also recomputes final histograms, label counts, bound arithmetic and witnesses. Stable equitability alone is insufficient: arbitrary individualization could make an unsafe, excessively loose ceiling, so justified-split replay is essential.

## Data and acceptance tests

Reuse the v1 strict training JSON and actual feature precision. No implicit feature binning, removal of model inputs or new graph semantics.

- Compare all 5,265 existing independent oracle pairs with the summary engine.
- Check feature/node/graph permutations, actual float precision, signed zero, labels excluded from refinement, empty graphs and zero-dimensional vectors.
- Replay valid certificates; reject arbitrary over-splitting, missing/moved/duplicated vertices, incorrect splitters, wrong counts, early stops and changed labels/bounds.
- Compare majority counts/classes with the synchronous engine, independent of numeric palette IDs.
- Measure difficult paths, regular graphs and diverse actual features, including certificate replay and peak RSS. Do not raise public budgets solely because one easy graph completes.

## Real-data evidence

Run fixed, recorded training selections from PROTEINS and/or ENZYMES with continuous node attributes enabled and actual exported tensors retained. Both have node attributes and no listed edge attributes in the [TU dataset catalogue](https://chrsmrrs.github.io/datasets/docs/datasets/). Record PyG loader settings/versions, raw-file digests for provenance only, actual `x`, supported graph fields, preprocessing and selection. Report a 100% ceiling honestly if that is the result. No raw dataset redistribution is required for the experiment report; scripts fetch from the original source.

## Hosting

The full Python service needs a container-capable host. Render integration has been discovered and suggested; connection is a separate user action. Continue implementing/verifying while connection is pending. Avoid replacing the working API with a static screenshot or claiming a deployed backend before its actual hosted workflow passes.
