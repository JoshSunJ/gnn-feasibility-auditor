# SWE release tracker

Work started 2026-10-12. The verified prototype is preserved on `main`; implementation proceeds on `feature/swe-release` with focused commits. Public hosting remains gated by validation.

| Step | Acceptance criterion | Status |
|---|---|---|
| 1. Preserve and track | Baseline Git commit, private GitHub repository, scoped release branch | Complete: baseline `dab7c26`; private JoshSunJ/gnn-feasibility-auditor |
| 2. Bounded audit API | Strict raw JSON ingestion, killable processes, queue limits, cancellation, expiry, verified downloads, incomplete results never show a ceiling | Complete locally: 9 service tests pass, including actual spawned workers |
| 3. Complete interface | Demo/upload, readable validation errors, live job state, conflict comparison, node features, exact exports, mobile layout | Pending |
| 4. Input integration | Optional in-memory PyG adapter preserves supported actual inputs and rejects unsupported model inputs | Pending |
| 5. Verification | Core/oracle/property/API/failure/browser tests, measured time and memory, packaged CLI smoke check | Pending |
| 6. Delivery | Locked dependencies, CI, Docker, Render configuration, operating guide | Pending |
| 7. Review and handoff | GitHub issue/PR tracking, passing CI, honest release evidence and remaining limitations | Pending |
| 8. Public deployment | Tested Linux container, capacity/failure gates and hosting access available | Pending |

The SWE release focuses on a reliable auditing workflow. Real-data ML studies are separate work and must not be represented as completed. Synthetic fixtures establish correctness examples, not real-world predictive performance.

Each step records its evidence here and in VERIFICATION.md. GitHub tracking must reflect actual checked results; it must not close work merely because code exists.
