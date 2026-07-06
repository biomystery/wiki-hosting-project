---
type: concept
aliases:
  - Consistent hashing
  - sharding
  - hash ring
tags:
  - wiki
  - concept
  - partitioning
created: 2026-02-01T10:00
updated: 2026-02-01T10:00
---
# Consistent hashing

Maps keys to nodes on a ring so that adding or removing a node only remaps a small fraction of
keys. [[Meridian]] uses virtual nodes for even load. This is the "sharding" layer owned by
[[Rohan Mehta]].

Popularized for KV stores by [[DeCandia2007_Dynamo]]. Each partition is then made durable and
ordered via [[Raft consensus]].

See also: [[Meridian MOC]].
