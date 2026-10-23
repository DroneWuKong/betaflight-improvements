# Larger proposals

## Complete Blackbox mode visibility

Source: [mode flags above 31](https://github.com/betaflight/betaflight/issues/8230).
The current slow-history `flightModeFlags` field is 32 bits, copied from the
mode activation mask. Extending it changes an interface consumed by log readers.

Before implementing, compare a wider encoding with an additional high-word
field. Review Blackbox Explorer and other decoder behavior, recording overhead,
and old-reader compatibility. Acceptance requires fixtures with modes below and
above bit 31, stable low-word decoding, explicit behavior in older readers,
and a documented migration strategy. Do not silently reinterpret old logs.

## Read-only MSP display access

Source: [port-scoped MSP command restrictions](https://github.com/betaflight/betaflight/issues/15752).
A display should be able to read the information it needs without automatically
receiving the same configuration privileges as a trusted configurator.

Inventory required query commands, protocol versions, error responses, and
display compatibility. Check whether the current architecture can apply a
policy per serial port. Acceptance requires allowed queries to keep working,
rejected writes to leave settings unchanged, mixed MSP v1/v2 coverage, and
compatibility tests for supported displays. Search for related work before
choosing a command list or changing firmware defaults.

## Rolling storage compatibility

Source: [existing ring-buffer implementation proposal](https://github.com/betaflight/betaflight/pull/15197).
Start with the existing proposal and its companion configurator work. Assess
download discovery, wrap ordering, partial logs, interrupted reads, storage
identity, and backward compatibility. A useful contribution could be a shared
fixture set and compatibility tests rather than a separate ring implementation.

Acceptance: record exact firmware/reader revisions, preserve current linear
downloads, distinguish complete and partial captures, and verify wrapped-log
ordering in host fixtures before physical flash tests.
