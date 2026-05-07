# ADR 002: Playwright in isolated Docker sidecar

**Date:** 2026-05-07  
**Status:** Accepted

## Context
Booking automation requires driving a headless browser (Playwright/Chromium). Chromium is memory-heavy (~300MB), crashes unpredictably, and has a different update cadence from the Python app.

## Decision
Run Playwright as a separate Docker container exposing an internal HTTP API (`POST /add-to-cart`). The app container calls it via httpx. The sidecar never exposes ports outside the Docker network.

## Consequences
- A Chromium crash cannot kill the APScheduler process or corrupt the DB
- Playwright and its browser can be updated independently
- Adds Docker Compose complexity (two services instead of one)
- The app must handle sidecar unavailability gracefully (non-fatal — falls back to notify-only)
