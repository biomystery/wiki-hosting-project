---
type: concept
aliases:
  - Raft
  - Raft consensus
  - leader election
tags:
  - wiki
  - concept
  - consensus
created: 2026-02-01T10:00
updated: 2026-02-01T10:00
---
# Raft consensus

Leader-based consensus protocol that keeps [[Meridian]]'s replication log identical across
replicas. One leader per partition accepts writes, appends them to the [[Write-ahead log]], and
replicates to followers; a majority ack commits the entry.

Defined in [[Ongaro2014_Raft]]. Contrast with the leaderless, eventually-consistent approach of
[[DeCandia2007_Dynamo]].

Write throughput is bounded by the leader — see [[throughput-bench-2026]].

See also: [[Meridian MOC]].
