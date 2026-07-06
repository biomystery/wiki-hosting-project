---
type: experiment
aliases:
  - throughput-bench-2026
  - throughput benchmark
tags:
  - wiki
  - experiment
created: 2026-02-05T10:00
updated: 2026-02-10T16:00
---
# Throughput benchmark 2026

Measured read/write throughput of [[Meridian]] versus cluster size (3–9 nodes).

- **Reads** scaled roughly linearly with replica count.
- **Writes** were bounded by the partition leader, as predicted by [[Raft consensus]].

Run by [[Ada Lindqvist]]. Follow-up: revisit under [[multiregion-replication]].

See also: [[Meridian MOC]].
