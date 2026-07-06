---
type: project
aliases:
  - Meridian
  - Meridian KV
tags:
  - wiki
  - project
created: 2026-01-05T09:00
updated: 2026-02-18T14:30
---
# Meridian — distributed key-value store

Meridian is a fictional distributed KV store used here as synthetic test content. It stores
keys across a cluster, replicates each partition for durability, and keeps replicas in sync.

## Write path
A client write is routed to the owning node via [[Consistent hashing|the hash ring]], appended
to the [[Write-ahead log]] for durability, then committed through [[Raft consensus]] so every
replica agrees on order. The design borrows partitioning ideas from [[DeCandia2007_Dynamo]] and
the consensus protocol from [[Ongaro2014_Raft]].

## Read path
Reads go to any in-sync replica of the owning partition. Consistency level is tunable.

## Team
Maintained by [[Ada Lindqvist]] (consensus, storage) and [[Rohan Mehta]] (sharding, clients).

## Related work
- [[throughput-bench-2026]]
- [[multiregion-replication]]

See also: [[Meridian MOC]].
