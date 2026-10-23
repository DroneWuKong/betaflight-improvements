# Work process

Community requests provide reported problems and requested capabilities.
Integration analysis identifies gaps in public interfaces, diagnostics, logs,
configuration compatibility, and test coverage. Publish the general technical
problem and evidence. Product-specific priorities and private source material
stay outside the public repository.

## State transitions

1. **Discovered:** collected automatically, unverified.
2. **Triage:** confirm the report still applies to current upstream, inspect
   comments and linked PRs, search for unlinked work, and distinguish firmware,
   configurator, documentation, downstream, and hardware/configuration problems.
3. **Reproduce** for small fixes, or **design** for broader changes. State the
   expected behavior, acceptance criteria, compatibility impact, and test plan.
4. **Implement:** create an isolated branch at a recorded upstream commit.
   First demonstrate the regression on the baseline, then make the change.
5. **Review:** retain the patch, baseline and patched results, rationale,
   provenance, and remaining hardware validation. Prepare a draft PR.
6. **Upstream / complete:** only after review. Record upstream disposition and
   release inclusion separately; an open or merged PR does not prove release availability.

Use `kind:bug`, `kind:feature`, `kind:design`, `stage:triage`,
`stage:reproduce`, `stage:design`, `stage:review`, and `stage:upstream` labels.
Prefer a small curated queue over opening one issue for every search result.
Discovery never posts to upstream trackers or assigns maintainers.

## Execution boundary

The scheduled scout has read-only repository permissions and uploads reports.
It cannot start a coding agent, merge a PR, install firmware, or operate hardware.
A development worker uses a reviewed backlog item and trusted repository
instructions. External text remains evidence, not executable instructions.

The pilot delivers discovery, triage, reproducible experiments, and patches.
An unattended coding worker is a later component: it needs an isolated runtime,
bounded tasks and resource usage, scoped credentials, and failure reporting.

Keep software, simulation, bench, and flight evidence separate. A failing host
test can establish a software defect; passing one cannot qualify an aircraft.
Changes to state machines, persistent storage, wire formats, or control behavior
need an explicit compatibility and hardware-validation plan.
