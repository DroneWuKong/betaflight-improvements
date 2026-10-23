# SDIO timeout rollover experiment

**Status: host-tested patch for review. No target build, bench test, or flight
qualification is claimed.** This is a narrow arithmetic fix, not a complete
solution to [the read-error recovery issue](https://github.com/betaflight/betaflight/issues/8690).

## Problem

`timeMs_t` and the operation start time are 32-bit unsigned values. The current
read, write-completion, and multi-block-stop paths compare the clock with an
absolute deadline formed by adding a timeout to the start time. Just before
clock rollover, that deadline wraps first. A still-pending operation can be
treated as expired. The read case enters the existing same-poll error loop;
the two write paths can reset prematurely.

The patch compares unsigned elapsed time with the timeout, matching the
initialization-timeout pattern already used by this function. It preserves the
existing exact-deadline behavior (`<=` for reads, `>` for writes).

## Reproduce

The exact upstream revision is in [upstream.json](upstream.json). Use a checkout
containing that revision; the verifier reads it with `git show` and does not
modify the checkout. Requires Python 3.10+, Git, and a host C compiler named `cc`.

```sh
python3 experiments/sdio-timeout/verify.py /path/to/betaflight
```

The verifier applies [timeout-rollover.patch](timeout-rollover.patch) in a
temporary directory. It extracts the **actual production polling function**
from baseline and patched sources, reads state enums and timeout constants from
the pinned source, and compiles each with host hardware/time stubs.

Observed result on GupB: the baseline fails `read-before-wrap`,
`write-before-wrap`, and `stop-before-wrap`; the other 10 controls pass.
The patch passes all 13 cases. A bounded read stub exits with code 73 if the
poll retries repeatedly, so a baseline regression cannot hang the test runner.
Each executable also has a process timeout.

Controls cover normal pending reads, exact deadlines, clocks before and after
rollover, genuine write expiration, successful reads, and disabled storage.

## Scope and related work

The harness compiles the polling function with boundary stubs, **not the full
firmware or complete hardware driver**. It does not test DMA cancellation,
peripheral recovery, physical storage, or real scheduler timing. Genuine
read-error recovery remains separate.

[The open SDIO recovery PR](https://github.com/betaflight/betaflight/pull/15748)
already addresses the broader retry-loop problem. Its inspected diff still
uses absolute timeout comparisons and adds another write timeout. Reconcile
this patch with that work before upstream submission, and extend its full-driver
suite with rollover cases. No upstream PR or issue comment has been submitted
by this experiment.

Sources: [production driver](https://github.com/betaflight/betaflight/blob/c1a17eca71b6cefe5224eb4c3d3aab587cf1b802/src/main/drivers/sdcard_sdio_baremetal.c),
[time types](https://github.com/betaflight/betaflight/blob/c1a17eca71b6cefe5224eb4c3d3aab587cf1b802/src/main/common/time.h).

Code and patch: GPL-3.0-or-later; see repository COPYING.
