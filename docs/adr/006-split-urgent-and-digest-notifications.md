# ADR 006: Split Urgent and Digest Notifications

## Status

Accepted — 2026-05-08

## Context

The M5 runner sent one notification per available site found. A typical first-run
scan against a popular rec area returns 21+ available campsites, generating 21+
emails in under a minute. Two problems:

1. Inbox spam, Gmail rate-limit risk.
2. The time-critical signal — "auto-cart-add succeeded, complete payment within
   15 minutes" — is diluted by 20 lower-priority "available, not carted"
   notifications. The user can't visually distinguish them.

The booking sidecar's 15-minute cart hold is the highest-value signal CampBuddy
produces. It must remain prominent.

## Decision

Split notifications by urgency:

- **Urgent path:** When `cart_added=True`, call `notify()` immediately inline
  within the runner's per-site loop, one message per carted site.
- **Digest path:** All non-carted sites from a scan run are buffered and flushed
  as a single multi-site email and/or Telegram message after the per-site loop.

Implementation: `core/notifier.py` exposes `notify` (existing, single-payload,
urgent) and `notify_digest` (new, list-of-payloads). `core/runner.py` routes
per-site after the cart-add attempt.

## Rejected Alternatives

- **One email per scan run for everything.** Flattens urgency; user must scan
  body to find carted sites needing immediate payment.
- **Configurable `notify_mode: per_site | split | digest`.** YAGNI. The split
  design is strictly better than per-site for every realistic case.

## Consequences

**Positive:**
- Inbox volume drops from O(N sites) to O(N carted + 1) per run.
- 15-minute booking signal stays prominent — it lives in its own dedicated message.
- Digest format scales gracefully (1 site or 100 sites — same UX).
- Telegram 4096-char limit handled by truncation in the digest formatter.

**Negative:**
- Two notification paths to maintain.
- Non-urgent notifications are deferred until end of run (~30s for 21 sites with
  the Playwright sidecar). Acceptable since they aren't time-critical.

## Related

- [ADR 004: Notify even when cart add fails](004-notify-on-cart-failure.md) —
  established that not-carted notifications are valuable. This ADR refines
  *how* they are delivered.
