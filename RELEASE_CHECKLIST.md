# SWE release tracker

## Hosted follow-up

Render/GitHub access is connected and the Free/manual Docker service is online. The actual host passed HTTPS/export/replay, invalid input, timeout-without-result, real 15-minute expiry, restart invalidation, overload and four-job cancellation checks. Both real datasets and a 50,000-node path completed with the measured 90-second host budget. A final v0.3.1 patch tightens report-label types and percentage display; its release PR tracks CI and final manual deployment. No always-on SLA, real-data model training, paid compute or public source repository is claimed.

## v0.3 scale and live-release follow-up

Branch: `feature/scale-and-live-release`. Hosting is authorized by the user; account access is still required. The private repository stays private.

| Step | Evidence | State |
|---|---|---|
| Research and compact exact engine | SCALE_RESEARCH.md; 5,265 independent oracle pairs; separate justified-split replay, tamper and stability checks | Complete locally |
| Actual-feature studies | PROTEINS/ENZYMES fixed training selections: 1,370 graphs, 49,579 nodes; both 100% ceilings honestly recorded | Complete |
| Larger bounded service | 50,000-node synthetic paths/cycles/unique features and both real inputs completed in three local repetitions; actual 50k-node Linux Docker path completed; streamed exports, bounded upload buffers | Complete locally and in Linux CI; target-host capacity remains separate |
| Usable large-data inspection | Mode choice, final-only compact view, conflict/ID filtering, class/color pagination and full node-ID search | 8 component tests, 6 Linux browser workflows, complete local PROTEINS upload and mobile checks passed |
| Review and Linux packaging | Focused commits, PR #4 merged as `49bf443`, installed CLI + browser + 50k-node Linux Docker smoke | All 5 jobs passed for final branch `cdc9ebd` and merged `49bf443` |
| Live deployment | Free/manual Render Docker service and actual hosted checks | v0.3 online and checked; final v0.3.1 hardening promotion tracked separately |

The v0.2 release record below is historical. Real input audits now exist; real-data model training remains future work.

Work started 2026-10-12. The verified prototype is preserved on `main`; implementation proceeds on `feature/swe-release` with focused commits. Public hosting remains gated by validation.

| Step | Acceptance criterion | Status |
|---|---|---|
| 1. Preserve and track | Baseline Git commit, private GitHub repository, scoped release branch | Complete: baseline `dab7c26`; private JoshSunJ/gnn-feasibility-auditor |
| 2. Bounded audit API | Strict raw JSON ingestion, killable processes, queue limits, cancellation, expiry, verified downloads, incomplete results never show a ceiling | Complete locally: 9 service tests pass, including actual spawned workers |
| 3. Complete interface | Demo/upload, readable validation errors, live job state, conflict comparison, node features, exact exports, mobile layout | Complete locally: React/TypeScript/Cytoscape; 4 component tests; real file/demo, comparison, invalid-input and 390px browser checks |
| 4. Input integration | Optional in-memory PyG adapter preserves supported actual inputs and rejects unsupported model inputs | Complete locally: 4 adapter tests pass; PyG 2.8.1 |
| 5. Verification | Core/oracle/property/API/failure/browser tests, measured time and memory, packaged CLI smoke check | Complete: 40 Python + 4 frontend tests; four Linux browser workflows passed; capacity evidence saved |
| 6. Delivery | Locked dependencies, CI, Docker, Render configuration, operating guide | Complete: locked builds, Linux Docker and installed CLI smoke checks passed; hosted staging remains separate |
| 7. Review and handoff | GitHub issue/PR tracking, passing CI, honest release evidence and remaining limitations | Complete: PR #2 merged as `5fa4932` after all checks passed for `ca1deed`; main contains the full SWE application |
| 8. Public deployment | Tested Linux container, capacity/failure gates and hosting access available | Held: Render account/plan approval and hosted staging checks still required |

The SWE release focuses on a reliable auditing workflow. Real-data ML studies are separate work and must not be represented as completed. Synthetic fixtures establish correctness examples, not real-world predictive performance.

Each step records its evidence here and in VERIFICATION.md. GitHub tracking must reflect actual checked results; it must not close work merely because code exists.
