# ADR 004: Notify even when cart add fails

**Date:** 2026-05-07  
**Status:** Accepted

## Context
Playwright add-to-cart can fail for many reasons: bot detection, Recreation.gov UI changes, session timeout, login issues. Campsite windows close in minutes. If we only notify on successful cart add, a Playwright failure means the user never learns about availability.

## Decision
Always send a notification when a campsite is found, regardless of cart add outcome. The message indicates cart status and always includes the direct booking URL so the user can act manually.

## Consequences
- User is always informed, even when automation fails
- Playwright reliability is not critical-path — degraded gracefully
- Slightly noisier messages when cart add fails (mitigated by clear status line)
