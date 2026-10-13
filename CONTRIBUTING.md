# Working on the auditor

Use the exact core and verifier as the foundation. Change the mathematical contract before accepting a new kind of graph input. Never silently add or drop model inputs, use graph hashes as proof, cap refinement and declare equivalence, or describe the ceiling as test accuracy.

For core changes, extend the independent pairwise oracle and invariance/adversarial cases. For service changes, exercise actual workers, rejected inputs, incomplete states, cancellation, overload, restart and expiry. For interface changes, test raw input preservation and stale-result clearing; verify both desktop and mobile workflows. Completed reports must still independently replay against exported actual inputs.

Use a focused branch and commit each reviewable step. Run the relevant checks before pushing. The release workflow additionally checks Python 3.10/3.13, the installed CLI, service/property tests, component tests, TypeScript/build, real Chromium workflows, optional ML tools and the Linux Docker image. Keep validation descriptions specific to what actually passed.

See README.md for setup, OPERATIONS.md for service behavior, RELEASE_CHECKLIST.md for release gates and RESEARCH.md for assumptions/proof. Real-data studies are a separate milestone; preserve original features, training indices and preprocessing when adding them.
