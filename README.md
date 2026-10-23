# Betaflight Improvements

An independent community lab for useful bug fixes, feature proposals,
interoperability, diagnostics, and reproducible testing. Not an official
Betaflight project.

## Start here

- [Reviewed backlog](backlog/README.md): evidence, scope, and next actions.
- [Discovery runs](https://github.com/DroneWuKong/betaflight-improvements/actions/workflows/discover.yml): daily and manually triggered reports.
- [Work process](docs/WORKFLOW.md): discovery through implementation and review.
- [Issues](https://github.com/DroneWuKong/betaflight-improvements/issues): curated work tracking.

## Run discovery

Requires Python 3.10+ and either an authenticated GitHub CLI or a `GH_TOKEN`
with public repository read access. No third-party Python dependencies.

```sh
python3 -m unittest discover -s tests -v
python3 scout.py
```

Reports contain public issue/discussion titles, source links, topic scores,
and linked pull-request states. Raw bodies and comments are not saved. Reports
are written under ignored `reports/`; scheduled reports are Actions artifacts.

The first adapter reads Betaflight's public GitHub issues and discussions.
It samples oldest and newest issues, and the oldest discussion pages.
Pagination limits and failed requests are explicit. It does not read Discord,
private forums, or claim exhaustive coverage of all discussions.

The highest-ranked issues receive comment and timeline checks. A linked open
or merged PR is flagged for review; it is not assumed to fully solve the issue.
Discussion comments, unlinked PRs, release inclusion, and code verification
still need review. Scores measure keyword relevance, not implementation readiness.

## Project sequence

1. Betaflight: active pilot.
2. [ArduPilot](https://github.com/DroneWuKong/ardupilot-improvements): prepared tracking hub, next.
3. [PX4](https://github.com/DroneWuKong/px4-improvements): prepared tracking hub, third.

Small changes get focused regression tests and reviewable patches. Larger
requests get design proposals with compatibility, resource, and validation
requirements. Discovery runs automatically; code changes require a reviewed
task and a development worker. Nothing merges, publishes firmware, or flashes
hardware automatically.
