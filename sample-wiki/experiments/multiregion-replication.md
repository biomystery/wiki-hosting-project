---
type: experiment
aliases:
  - multiregion-replication
  - cross-region replication
tags:
  - wiki
  - experiment
created: 2026-02-15T10:00
updated: 2026-02-15T10:00
---
# Multi-region replication trial

Async log shipping of [[Meridian]] partitions across two regions, layered on top of
[[Raft consensus]] within each region. Goal: bound cross-region staleness under failover.

Owner [[Rohan Mehta]]. Builds on results from [[throughput-bench-2026]] and the availability
model of [[DeCandia2007_Dynamo]].

Status: **ongoing**.

See also: [[Meridian MOC]].
