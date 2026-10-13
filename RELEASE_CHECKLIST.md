# SWE release tracker

Work started 2026-10-12. The verified prototype is preserved on `main`; implementation proceeds on `feature/swe-release` with focused commits. Public hosting remains gated by validation.

| Step | Acceptance criterion | Status |
|---|---|---|
| 1. Preserve and track | Baseline Git commit, private GitHub repository, scoped release branch | Complete: baseline `dab7c26`; private JoshSunJ/gnn-feasibility-auditor |
| 2. Bounded audit API | Strict raw JSON ingestion, killable processes, queue limits, cancellation, expiry, verified downloads, incomplete results never show a ceiling | Complete locally: 9 service tests pass, including actual spawned workers |
| 3. Complete interface | Demo/upload, readable validation errors, live job state, conflict comparison, node features, exact exports, mobile layout | Complete locally: React/TypeScript/Cytoscape; 4 component tests; real file/demo, comparison, invalid-input and 390px browser checks |
| 4. Input integration | Optional in-memory PyG adapter preserves supported actual inputs and rejects unsupported model inputs | Complete locally: 4 adapter tests pass; PyG 2.8.1 |
| 5. Verification | Core/oracle/property/API/failure/browser tests, measured time and memory, packaged CLI smoke check | Complete: 40 Python + 4 frontend tests; four Linux browser workflows passed; capacity evidence saved |
| 6. Delivery | Locked dependencies, CI, Docker, Render configuration, operating guide | Complete: locked builds, Linux Docker and installed CLI smoke checks passed; hosted staging remains separate |
| 7. Review and handoff | GitHub issue/PR tracking, passing CI, honest release evidence and remaining limitations | Issue #1 and PR #2 created; final evidence/review pending |
| 8. Public deployment | Tested Linux container, capacity/failure gates and hosting access available | Held: Render account/plan approval and hosted staging checks still required |

The SWE release focuses on a reliable auditing workflow. Real-data ML studies are separate work and must not be represented as completed. Synthetic fixtures establish correctness examples, not real-world predictive performance.

Each step records its evidence here and in VERIFICATION.md. GitHub tracking must reflect actual checked results; it must not close work merely because code exists.
