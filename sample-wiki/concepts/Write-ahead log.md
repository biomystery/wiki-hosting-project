---
type: concept
aliases:
  - WAL
  - Write-ahead log
  - write ahead logging
tags:
  - wiki
  - concept
  - storage
created: 2026-02-01T10:00
updated: 2026-02-01T10:00
---
# Write-ahead log

Durability primitive: every mutation is appended to an on-disk log before the in-memory state
is updated, so a crash can be recovered by replay. In [[Meridian]] the WAL sits beneath the
storage engine and feeds [[Raft consensus]] replication.

Owned by [[Ada Lindqvist]].

See also: [[Meridian MOC]].
