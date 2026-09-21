# Debugging with Grafana

CampBuddy's containers ship logs and infra metrics to **Grafana Cloud**
(`onurburak9.grafana.net`). Claude Code can query them directly through the
Grafana MCP server (see [Setup](#setup)). Use this when debugging runtime
behaviour that logs alone (`docker compose logs`) can't show — historical
issues, cross-container correlation, or resource problems.

## What's actually in Grafana

| Signal | Datasource (uid) | Source | Use for |
|--------|------------------|--------|---------|
| **Logs** | `grafanacloud-logs` (Loki) | container stdout | scan runs, booking attempts, notifier errors, tracebacks |
| **Metrics** | `grafanacloud-prom` (Prometheus) | Docker integration (`job=integrations/docker`, cadvisor) | container CPU / memory / network / fs, crash loops, OOMs |

**Containers** (label `container` in Loki, label `name` in Prometheus):

| Container | Component | Look here for |
|-----------|-----------|---------------|
| `campbuddy-app-1` | scheduler (`main.py`) | scan cycles, availability checks, booking, notifications |
| `campbuddy-api-1` | FastAPI (`api/`) | REST/auth requests, API errors |
| `campbuddy-frontend-1` | nginx + React SPA | static serving, proxy errors |
| `campbuddy-playwright-1` | Playwright sidecar | browser automation, cart/add failures |

**What is NOT available:** no Prometheus app-level metrics (no counters or
histograms — the app exposes no `/metrics` endpoint), and no traces from
campbuddy (a Tempo datasource exists but campbuddy sends nothing to it).
Prometheus metrics are container-resource only.

**Structured app events are available in Loki.** The scheduler emits logfmt
event lines that `| logfmt` parses into fields, so LogQL metric queries give
you counts, rates and alerts without any Prometheus instrumentation — see
[Cart-add outcomes](#cart-add-outcomes).

## Loki (logs) — LogQL

Loki labels: `container, instance, job, service_name, stream`.

```logql
# All logs from the scheduler
{container="campbuddy-app-1"}

# Errors across every campbuddy container
{container=~"campbuddy-.*"} |~ "(?i)error|exception|traceback"

# Booking / Playwright failures
{container=~"campbuddy-(app|playwright)-1"} |~ "(?i)book|cart|playwright"

# stderr only (stream label)
{container="campbuddy-app-1", stream="stderr"}
```

Tip: narrow the time range — Loki queries scan by time, and campbuddy is
low-volume, so `now-6h` or `now-24h` is usually enough.

## Cart-add outcomes

`core/events.py` emits one logfmt line per cart-add attempt from
`campbuddy-app-1`. This is the signal to use when asking "is add-to-cart
actually working?" — `cart_added=False` in the database alone can't tell a
genuine failure from a site that was never attempted.

```
event=cart_add result=success scan_id=12 campsite_id=42210 duration_ms=18004
event=cart_add result=failure scan_id=12 campsite_id=42035 reason=button_disabled duration_ms=4120 error="Add to Cart is disabled for these dates"
event=cart_add result=skipped scan_id=12 reason=over_cap capped=5 found=69
```

| Field | Notes |
|-------|-------|
| `result` | `success` \| `failure` \| `skipped` |
| `reason` | closed set, safe as a label (see below) |
| `error` | raw sidecar message, whitespace-collapsed to one line |
| `duration_ms` | per-site, measured in the sidecar |

Reason codes: `button_disabled` (already held or unbookable), `no_redirect`
(click didn't reach order details), `login_failed` (Recreation.gov rejected
the sign-in), `sidecar_unavailable`, `sidecar_error`, `over_cap`, `unknown`.
Keep this set small — it is used as a Grafana label. The full message lives in
the `error` field and in `scan_results.cart_error`.

```logql
# Success vs failure over the last hour
sum by (result) (count_over_time(
  {container="campbuddy-app-1"} | logfmt | event="cart_add" [1h]))

# Why are cart-adds failing?
sum by (reason) (count_over_time(
  {container="campbuddy-app-1"} | logfmt
  | event="cart_add" | result="failure" [24h]))

# Failure ratio (0-1)
sum(count_over_time({container="campbuddy-app-1"} | logfmt | event="cart_add" | result="failure" [1h]))
/
sum(count_over_time({container="campbuddy-app-1"} | logfmt | event="cart_add" | result=~"success|failure" [1h]))

# p95 cart-add latency
quantile_over_time(0.95,
  {container="campbuddy-app-1"} | logfmt | event="cart_add"
  | unwrap duration_ms [1h])

# Everything that failed for one scan
{container="campbuddy-app-1"} | logfmt | event="cart_add" | scan_id="12" | result="failure"
```

### Alerting

No Prometheus needed — point a Grafana alert rule at the Loki datasource:

```logql
sum(count_over_time({container="campbuddy-app-1"} | logfmt
    | event="cart_add" | result="failure" [15m])) > 3
```

`reason="login_failed"` is the one worth paging on: it means Recreation.gov
started rejecting sign-ins, which is how the last outage began. Note that
cart-adds are sparse (a handful per scan interval), so use `count_over_time`
windows of 15m or more rather than `rate()`.

If you later want 13-month retention or cheaper wide-range queries, the
`reason` codes are already low-cardinality and map straight onto
`cart_add_total{result,reason}` — that needs a `/metrics` endpoint in
`main.py` plus a scrape config in the Grafana Cloud agent.

## Prometheus (metrics) — PromQL

Container label is `name` (not `container`). Available `container_*` metrics:
`container_cpu_usage_seconds_total`, `container_memory_usage_bytes`,
`container_last_seen`, `container_fs_usage_bytes`,
`container_network_{receive,transmit}_bytes_total` (+ error/drop counters),
`container_spec_memory_reservation_limit_bytes`.

```promql
# Memory per campbuddy container
container_memory_usage_bytes{name=~"campbuddy-.*"}

# CPU cores used (rate over 5m)
rate(container_cpu_usage_seconds_total{name=~"campbuddy-.*"}[5m])

# Is a container alive / restarting? (gap => not seen)
time() - container_last_seen{name="campbuddy-app-1"}
```

## Debugging playbook

- **Scan not finding / booking sites** → `campbuddy-app-1` logs, filter for the
  scan id or campground; check `campbuddy-playwright-1` for cart failures.
- **No notification received** → `campbuddy-app-1` logs, filter `notifier` /
  `smtp` / `telegram`.
- **API/UI broken** → `campbuddy-api-1` (500s, auth) then `campbuddy-frontend-1`.
- **App crash-looping / slow** → Prometheus `container_last_seen` gaps +
  `container_memory_usage_bytes` near the reservation limit.

## Setup

The MCP server is configured in [`.mcp.json`](../../.mcp.json) (project root):
`uvx mcp-grafana --disable-write` (read-only), `GRAFANA_URL` inline, token via
env var. The **service account token is never stored in the repo** — export it
in your shell so Claude Code inherits it at launch:

```bash
# ~/.zshrc  (Grafana → Administration → Service accounts → Viewer role → token)
export GRAFANA_SERVICE_ACCOUNT_TOKEN=glsa_...
```

Then start Claude Code from that shell and run `/mcp` to approve + verify the
`grafana` server. `--disable-write` keeps it read-only; drop that flag only if
you want Claude to build/edit dashboards.
