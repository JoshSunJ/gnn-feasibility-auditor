# Exact 1-WL feasibility audit: claim and verification plan

This document defines the result before implementation. The core is verified before adding model benchmarks or a visual interface.

## Mathematical claim

Let the supplied training multiset be D = {(G_i, X_i, y_i)} for i = 1,...,N, N > 0. Every sample counts once, including duplicates. Each G is a finite simple undirected graph, and X contains the **actual input vector for every node**, after the same preprocessing and conversion to the declared numeric precision used by the model.

On the disjoint union of all input graphs, assign a common initial color to exactly equal feature vectors:

    c_0(v) = intern_exact(X_v)
    c_(t+1)(v) = intern_exact(c_t(v), multiset{c_t(u): u in N(v)})
    H_t(G) = multiset{c_t(v): v in V(G)}

Interning is injective on complete tuples, not a finite graph digest. All graphs share the same palette in each round. Let G ~ H when H_t(G) = H_t(H) for every t. Retaining the old color makes partitions refine monotonically. Once a round creates no new color classes, the partition is stable, so subsequent rounds cannot separate graphs with matching histograms. Exact equality of stable histograms is therefore sufficient.

For any deterministic message-passing classifier f in the scope below,

    G ~ H  =>  f(G, X_G) = f(H, X_H).

For each equivalence class C, let n_(C,y) count training labels y. Then

    training_accuracy(f, D) <= U(D) = (1/N) * sum_C max_y n_(C,y)
    unavoidable_training_errors >= N - sum_C max_y n_(C,y).

**Proof sketch.** At layer zero, equal colors have equal inputs. Inductively, equal refined colors imply equal previous states and equal multisets of neighbor states, so shared deterministic updates produce equal states. Equal color histograms imply equal multisets of node states and histories, hence equal invariant readouts and predictions. A classifier making one prediction for a class can correctly label at most that class's most frequent label. Sum over classes.

For topology-derived degree normalization, use the stable partition directly: equal stable colors imply equal features and degree and equal multisets of neighbor stable colors. Degrees are constant on each stable color. Induction over model layers on these stable colors therefore also covers symmetric GCN degree weights; a one-layer/one-round correspondence is not needed for the stable bound.

This upper bound is attained by an unrestricted lookup classifier on exact WL classes. It does **not** promise attainability by a particular architecture, depth, width, optimizer, or finite numerical implementation. WL-distinguishable graphs may still be indistinguishable to GCN, mean aggregation, or a shallow GNN. A ceiling of 100% is inconclusive.

## Scope and assumptions

- Same model parameters and evaluation behavior for every graph; one graph-level categorical target per sample; unweighted micro accuracy.
- Deterministic shared node updates and permutation-invariant multiset neighborhood aggregation and graph readout. Readout may use all layer histories. Degree-dependent normalization is covered by stable 1-WL, although it can change the correspondence between layer number and refinement round.
- No input graph identifiers, sample positions, training labels, individual node IDs, extra graph-level features, positional encodings, random node features, spectral/subgraph features, higher-order state, or graph-dependent preprocessing missing from X. IDs in the file are bookkeeping only.
- The prototype rejects directed graphs, parallel edges, self-loops, edge attributes, weights, and graph attributes. Auditing these requires an explicitly extended refinement rule matching the model's inputs. Internal uniform self updates are permitted by the mathematical update rule.
- Features are explicit finite float32 or float64 vectors of one declared dimension. No missing-feature defaults, degree substitution, tolerances, rounding bins, feature dropping, or implicit augmentation.
- Numeric equality is equality after conversion to the declared IEEE precision, with +0 and -0 treated equally. Decimal source spellings that convert to the same value have the same color. Features with different represented values have different colors, however close they are. NaN, infinities and conversion overflow are errors. Export features after preprocessing in the model's actual precision; decimal serialization must round-trip those values.
- The theorem concerns exact deterministic mathematical operations. Floating-point reduction order, stochastic evaluation, training-time dropout, context-dependent batching, and non-invariant implementations can create artifacts outside that statement. Benchmarks will evaluate deterministically and report numerical consistency checks separately.

Matching WL histograms certify **1-WL indistinguishability**, not graph isomorphism. Matching hashes alone certify neither. The bound describes the exact supplied training multiset; it is **not a test-accuracy prediction** or a data-generalization estimate. Continuous features often make colors unique and the bound uninformative; this is a legitimate result, not a reason to quantize them silently.

## Version 1 data contract

UTF-8 JSON, one object. Required top-level keys:

    {
      "schema_version": 1,
      "split": "train",
      "graph_type": "simple_undirected",
      "feature_dtype": "float64",
      "feature_dim": 1,
      "graphs": [
        {
          "id": "sample-a",
          "label": "connected",
          "nodes": [
            {"id": "u", "features": [1.0]},
            {"id": "v", "features": [1.0]}
          ],
          "edges": [["u", "v"]]
        }
      ]
    }

`feature_dtype` is `float32` or `float64`. `feature_dim` is a nonnegative integer; zero explicitly means actual zero-dimensional vectors, so every node must still provide `features: []`. Graph and node IDs are nonempty strings; graph IDs are globally unique and node IDs unique within a graph. Labels are strings or integers, with type preserved (the string "1" differs from integer 1); booleans and null are invalid. Isolated nodes must appear in `nodes`. Empty graphs are allowed. An empty dataset is rejected because accuracy is undefined. Endpoints must refer to declared nodes. Each unordered edge appears once. Unknown keys and duplicate JSON keys are rejected. Optional `description` strings are allowed on the dataset and graph objects for explanation, never as model inputs.

Explicitly declaring `split: train` prevents accidental interpretation of a mixed train/test file as training evidence. The exporter is responsible for choosing the training samples and matching the model inputs. The report repeats the contract and limitations.

## Core implementation plan

1. Dependency-free Python loader with strict validation and precision conversion.
2. Joint exact refinement with full tuple equality, neighbor multiplicities, and monotone stability detection. Store a per-round node-color and histogram trace.
3. Group graphs by exact stable histograms. Report the exact fraction, unavoidable errors, all class memberships and label counts, and bounded concrete cross-label witness pairs. Report omitted-pair counts explicitly.
4. Optional replayable certificate with initial represented features and every exact signature. Node and color IDs are local to a report, not reusable graph fingerprints.
5. Independent certificate verifier and correctness suite. Only after these pass: optional GIN/GCN training benchmarks and a local visual report/interface using the verified engine.

## Correctness tests and acceptance criteria

- C6 versus two disjoint triangles: uniformly featured six-node 2-regular graphs are indistinguishable at every round, despite different connectivity. Give opposing labels and verify the ceiling; include a same-label duplicate to test majority counting.
- P6 versus C6: initial features and node counts match, but degree refinement separates them. Graph size, degree and feature-histogram differences must separate as appropriate.
- Relabel node IDs and permute graph, node and edge order: equivalence partition and bound remain unchanged. Independently remapped palette IDs must not change the result.
- Feature-aware counterexample: perturb an actual feature so the former structural collision separates. Adjacent float64 values remain distinct; float32 conversion collisions and signed zero follow the documented semantics.
- A pair that separates only after multiple rounds defeats premature termination and capped-refinement claims. Every round's partition refines its predecessor; termination implies an equitable stable partition.
- Compare all pairs among all simple graphs through four vertices with a separate slow reference that runs pairwise refinement for a fixed safe number of rounds. Also compare seeded feature-labeled random graphs.
- Force tuple hash collisions in the intern table to confirm complete equality, not hash values, determines colors.
- Verify exact majority ceiling against brute-force predictions constant within each class. Include tied multiclass labels, typed labels, duplicate samples, isolated nodes, and empty graphs.
- Replay the certificate independently, reject tampering, and verify its bound and class memberships. End-to-end CLI tests cover text/JSON output and malformed input with a clean nonzero exit.
- Reject missing/nonfinite features, mixed dimensions, unsupported graph inputs, invalid endpoints, duplicate IDs/keys/edges, non-training split, and empty datasets.

Verification passes only when the independent oracle agrees, adversarial cases pass, certificate replay succeeds, and the demonstration's expected numerator/denominator and conflicts are reproduced. Tests validate this implementation; the proof and scope justify the mathematical implication.

## Primary references

- Xu, Hu, Leskovec and Jegelka, *How Powerful are Graph Neural Networks?*, ICLR 2019, Lemma 2 and Appendix A.1: https://cs.stanford.edu/people/jure/pubs/gin-iclr19.pdf . Establishes the aggregation-based GNN upper bound; the matching lower expressivity conditions are a separate result.
- Morris et al., *Weisfeiler and Leman Go Neural: Higher-Order Graph Neural Networks*, AAAI 2019: https://ojs.aaai.org/index.php/AAAI/article/view/4384 and https://arxiv.org/html/1810.02244 . Relates first-order GNN expressivity to color refinement and motivates higher-order models outside this auditor's scope.

The empirical training-ceiling formula and strict feature/serialization contract above are derived for this auditor, not quoted experimental results from those papers.
