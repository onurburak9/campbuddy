# ADR 001: Use camply as the availability engine

**Date:** 2026-05-07  
**Status:** Accepted

## Context
We need to check campsite availability across 20+ providers (Recreation.gov, ReserveCalifornia, GoingToCamp, state parks). Building provider-specific scrapers from scratch would take weeks and require ongoing maintenance as provider UIs change.

## Decision
Use [camply](https://github.com/juftin/camply) as a Python library via its OO API (`SearchRecreationDotGov(...).get_matching_campsites(continuous=False)`). We call it in single-check mode from our own scheduler rather than using its built-in continuous loop.

## Consequences
- 20+ providers work immediately with no additional code
- We are coupled to camply's versioning and API stability
- camply's internal logging/display output (rich) appears in our logs — acceptable
- We cannot use camply's built-in notifications (they conflict with our per-user dispatch logic)
- Adding a new provider is a one-line change in `PROVIDER_MAP`
- camply 0.34.1 pins pydantic v1 — see ADR 005 for impact
