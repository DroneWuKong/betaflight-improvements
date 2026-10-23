# Reviewed backlog

Initial review: October 22, 2026 (US Central); discovery follow-up October 23.
Upstream code inspected at
[`c1a17eca`](https://github.com/betaflight/betaflight/tree/c1a17eca71b6cefe5224eb4c3d3aab587cf1b802).
This is a curated queue; automatically collected items remain unverified.

| Priority | Work | Track | Established evidence | Next action |
| --- | --- | --- | --- | --- |
| 1 | [SDIO timeout calculations across clock rollover](https://github.com/DroneWuKong/betaflight-improvements/pull/6) | Small fix / review | The initial polling-function experiment fails three baseline scenarios and passes all 13 after the patch. A complete-driver follow-up against the recovery PR now covers its additional DMA-write timeout. | Review the draft patch package and revision-specific evidence; no hardware qualification claimed. |
| 2 | [SDIO read-error loop](https://github.com/betaflight/betaflight/issues/8690) | Follow existing work | Current error branch jumps back without changing read state. A broader search found [an open recovery fix](https://github.com/betaflight/betaflight/pull/15748). | Review that work and its hardware-boundary tests; avoid a competing recovery implementation. |
| 3 | [Rolling Blackbox storage](https://github.com/betaflight/betaflight/issues/13491) | Follow existing work | [Upstream ring-buffer PR](https://github.com/betaflight/betaflight/pull/15197) is open. | Review interoperability and log-download compatibility against that work; avoid a competing implementation. |
| 4 | [Blackbox modes beyond bit 31](https://github.com/betaflight/betaflight/issues/8230) | Design | Current slow-history field is uint32_t and copies only its own width from the activation mask. | Design writer/decoder compatibility and fixtures for higher mode bits. |
| 5 | [Read-only MSP access for display ports](https://github.com/betaflight/betaflight/issues/15752) | Design / triage | Public proposal found; collector found no explicit linked PR in inspected comments/timeline. | Review command surface, query compatibility, port scope, and existing unlinked work before implementation. |

## Work already in progress elsewhere

[Negative current missing a minus sign](https://github.com/betaflight/betaflight/issues/15855)
already has [an open fix](https://github.com/betaflight/betaflight/pull/15857).
It should be followed or reviewed rather than independently reimplemented.

The open SDIO recovery PR still uses absolute timeout deadlines in its inspected
diff. The rollover experiment is complementary, but its patch must be reconciled
with that PR before upstream submission. It does not claim to resolve the full
read-error-loop issue.

## Initial scan

The first run collected 282 distinct source records: public issues and
discussions, including inactive/answered discussions retained for context.
It exhausted the open issue endpoint in both chronological directions (192
records each, including pull requests filtered out afterward) and sampled 200
oldest discussions. More discussions exist. Request errors: zero.

The first 15 ranked open issues received comment/timeline checks. Several
linked PRs were identified. These checks do not establish that other items
have no existing solution. Each selected task still needs code inspection,
an additional PR search, and reproduction.

## Follow-up scan

The expanded October 23 scan collected 392 distinct source records with zero
request errors. It sampled 200 discussions in each chronological direction,
deduplicated the overlap, and refreshed the five watched issues independently
of ranking. It found the SDIO recovery PR through a scoped title search.

PR title searches are heuristic: for example, the SDIO query returned 20 of 30
matching PRs. Partial coverage is explicit, and matches do not establish that
a reported problem is solved. No automatic implementation approval is issued.
