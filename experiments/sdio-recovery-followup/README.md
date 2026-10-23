# Full-driver rollover follow-up

This complements the original [master-based experiment](../sdio-timeout/README.md)
by compiling the complete production driver against the existing
[SDIO recovery PR](https://github.com/betaflight/betaflight/pull/15748), pinned
at `88636558693693aca179631e9ed62a24b54f6569`.

The existing PR adds a DMA-write timeout which has the same absolute-deadline
rollover problem. The follow-up changes all four transfer timeout comparisons
to unsigned elapsed-time comparisons and adds eight tests to the PR's existing
11-test suite. The original recovery implementation and its tests belong to
that upstream contribution; this patch adds rollover coverage and arithmetic fixes.

## Reproduce

Requires Python 3.10+, Git, make, GCC, and G++. Tested locally with GCC 13.3.
The checkout must contain the pinned recovery commit. The verifier creates a
temporary local clone, leaving that checkout untouched.

```sh
python3 experiments/sdio-recovery-followup/verify.py /path/to/betaflight
```

It first adds only the regression tests and runs them against the upstream PR.
Then it applies the driver change and rebuilds with separate object directories.
The baseline must fail exactly four pending-operation rollover tests, while
the patched driver must pass all 19 tests. XML results, logs, compiler identity,
and the verdict are saved under ignored `reports/sdio-recovery/`.

Each pending-operation test checks elapsed time zero, one millisecond, one
millisecond before the deadline, and the exact deadline. Separate tests verify
expiration after rollover. Covered states: read, DMA write, write commit, and
multi-block stop.

## Validation limits

The complete C driver is compiled and linked through Betaflight's unit-test
build with hardware/time boundary stubs. This is stronger than the original
extracted-function experiment, but is still a host test: no target firmware
build, physical SD card, DMA cancellation, or flight qualification is claimed.
The upstream makefile labels GCC support experimental; CI records the same
compiler family explicitly. Preserve the original experiment and its evidence
as a separate revision-specific result.

Review and coordinate this follow-up with the upstream recovery work before
submission. No upstream message, merge, or firmware publication is performed.

Code and patch: GPL-3.0-or-later; see repository COPYING.
