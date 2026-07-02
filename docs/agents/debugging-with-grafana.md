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

**What is NOT available:** no app-level metrics (no scan-success or
booking-latency counters — the app doesn't emit any), and no traces from
campbuddy (a Tempo datasource exists but campbuddy sends nothing to it).
Metrics are container-resource only. If you need app KPIs, they must be
instrumented first (`/metrics` endpoint + Prometheus scrape).

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
