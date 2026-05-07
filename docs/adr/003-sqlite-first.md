# ADR 003: SQLite for Phase 1

**Date:** 2026-05-07  
**Status:** Accepted

## Context
We need persistent storage for users, scans, run history, and results. The service is single-process with no concurrent writers. User count is small (< 20 initially).

## Decision
Use SQLite with SQLAlchemy ORM. Database file mounted as a Docker volume at `./data/campbuddy.db`.

## Consequences
- Zero configuration, no separate DB container
- SQLAlchemy ORM means migration to PostgreSQL (Phase 2+) requires only changing `DATABASE_URL`
- `check_same_thread=False` needed for APScheduler's thread pool — safe because SQLAlchemy sessions are per-thread
- Must back up `campbuddy.db` file manually or via cron on the VPS
- Indexes on FK columns and composite (scan_id, campsite_id, booking_date) for dedup queries
