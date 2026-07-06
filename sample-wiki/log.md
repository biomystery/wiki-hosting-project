---
type: MOC
aliases:
  - log
  - changelog
tags:
  - wiki
  - log
created: 2026-01-05T09:00
updated: 2026-02-18T14:30
---
# Operational log

Append-only. Latest first.

## [2026-02-18] update | Meridian overview refreshed
- Expanded [[Meridian]] with the read path; linked [[Consistent hashing]] and [[Raft consensus]].

## [2026-02-15] experiment | multiregion replication started
- Kicked off [[multiregion-replication]]; async log shipping across two regions. Owner [[Rohan Mehta]].

## [2026-02-10] experiment | throughput benchmark complete
- [[throughput-bench-2026]] finished; linear read scaling to 9 nodes, write bound by leader. See [[Raft consensus]].

## [2026-02-01] concept | consensus & storage pages
- Created [[Raft consensus]], [[Consistent hashing]], [[Write-ahead log]]. Refs: [[Ongaro2014_Raft]], [[DeCandia2007_Dynamo]].

## [2026-01-05] init | wiki seeded
- Seeded index, MOC, and people pages ([[Ada Lindqvist]], [[Rohan Mehta]]).
