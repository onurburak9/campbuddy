# VPS Deployment (CI/CD via GitHub Actions)

CampBuddy redeploys automatically whenever a commit lands on `main` **and** the
tests + migration checks pass. Images are built once on the GitHub runner,
pushed to the GitHub Container Registry (GHCR), and pulled on the VPS — the VPS
never builds anything.

## How It Works

```
push to main
      │
      ▼
.github/workflows/ci.yml
  ┌────────┐   ┌──────────────┐
  │  test  │   │  migrations  │     (also run on every PR)
  └───┬────┘   └──────┬───────┘
      └───────┬───────┘
              ▼   needs: [test, migrations]  +  only on push to main
        ┌──────────┐
        │  build   │  build 3 images, push to GHCR, tagged :<commit-sha> and :latest
        └────┬─────┘
             ▼   needs: build
        ┌──────────┐
        │  deploy  │  SSH to VPS → git pull → docker compose pull → up -d
        │          │  → health check → prune
        └──────────┘
```

The VPS never contacts GitHub — GitHub contacts the VPS over SSH. A commit that
fails tests or the migration check never reaches the `build`/`deploy` stage.

### Why build in CI instead of on the VPS

- The VPS doesn't burn CPU/RAM building images (the Playwright image is heavy and
  can OOM a small box).
- Every deploy is an **immutable, versioned artifact** (tagged by commit SHA),
  so rollback is a one-liner (see [Rollback](#rollback)).
- Buildx layer caching in CI keeps repeat deploys fast.

### The three images

| Image | Services | Build context / Dockerfile |
|-------|----------|----------------------------|
| `ghcr.io/onurburak9/campbuddy` | `app`, `api` (same image) | `.` / `Dockerfile` |
| `ghcr.io/onurburak9/campbuddy-frontend` | `frontend` | `./frontend` / `frontend/Dockerfile` |
| `ghcr.io/onurburak9/campbuddy-playwright` | `playwright` | `.` / `playwright_service/Dockerfile` |

`docker-compose.yml` references each with `image: …:${CAMPBUDDY_TAG:-latest}`.
The deploy exports `CAMPBUDDY_TAG=<commit-sha>` so all four services pull the
exact build for that commit. The `build:` blocks remain so `docker compose build`
still works for local development.

---

## One-Time Setup

### Prerequisites

- A VPS with Docker + Docker Compose installed and a **git checkout of this repo**
  already present (the deploy does `git pull` there to update the compose file).
- SSH access to the VPS (you can already `ssh user@your-vps`).
- Admin access to the GitHub repository (to add secrets/variables).

### Step 1 — GHCR (no action needed)

The images live in the GitHub Container Registry under `ghcr.io/onurburak9/…`
and stay **private**. There's nothing to configure and nothing to make public:
the `build` job pushes with the workflow's built-in `GITHUB_TOKEN`, and the
`deploy` job passes that same short-lived token to the VPS so `docker compose
pull` can authenticate. The token is valid only for the duration of the job, and
the deploy script runs `docker logout` when it's done.

### Step 2 — Generate a dedicated deploy SSH keypair

On your **local machine** (not the VPS). A dedicated key can be revoked without
touching your personal key.

```bash
ssh-keygen -t ed25519 -C "campbuddy-deploy" -f ~/.ssh/campbuddy_deploy
```

Authorize the public key on the VPS:

```bash
ssh-copy-id -i ~/.ssh/campbuddy_deploy.pub user@your-vps
# verify:
ssh -i ~/.ssh/campbuddy_deploy user@your-vps "echo ok"   # should print: ok
```

### Step 3 — Add GitHub secrets and variables

**Settings → Secrets and variables → Actions.**

Secrets (**Secrets** tab):

| Secret | Value |
|--------|-------|
| `VPS_HOST` | VPS IP or hostname, e.g. `203.0.113.42` |
| `VPS_USER` | SSH user, e.g. `ubuntu` |
| `VPS_SSH_KEY` | Full contents of `~/.ssh/campbuddy_deploy` (the private key, including the BEGIN/END lines) |

Variable (**Variables** tab — not sensitive, so it lives here):

| Variable | Value |
|----------|-------|
| `VPS_APP_DIR` | Absolute path to the repo checkout on the VPS, e.g. `/home/ubuntu/campbuddy` |

### Step 4 — First deploy

Push any commit to `main` (or re-run the latest `CI` run). Watch **Actions → CI**:
`test` and `migrations` run first, then `build`, then `deploy`. The deploy logs
show the SSH connection, `docker compose pull`, `up -d`, and the health check.

Confirm on the VPS:

```bash
cd $VPS_APP_DIR
docker compose ps          # all services running/healthy
docker compose logs --tail=20 app
```

---

## What Happens During a Deploy

On the VPS, the `deploy` job runs:

1. `git pull origin main` — updates the compose file/config (no building).
2. `export CAMPBUDDY_TAG=<commit-sha>` — pins every service to this build.
3. `docker compose pull` — fetches the pre-built images from GHCR.
4. `docker compose up -d` — recreates changed containers; unchanged ones stay up.
5. **Health check** — fails the job (with recent logs) if any service isn't
   `running`, or if any healthcheck reports `unhealthy`.
6. `docker image prune -f` — reclaims dangling layers.

Migrations run automatically inside the `app` container's `entrypoint.sh`
(`alembic upgrade head`) before the scheduler starts — see
[Schema Changes](agents/schema-changes.md). Because `set -e` is in the
entrypoint, a failed migration crashes the `app` container, which the deploy
health check catches. For **riskier** migrations (NOT NULL backfills, large index
rebuilds), run them explicitly first as described in that doc.

Total downtime is the few seconds Docker takes to swap containers.

---

## Rollback

Every image is tagged by commit SHA, so rollback needs no rebuild. `docker image
prune -f` only removes *dangling* (untagged) layers, so recently-deployed
SHA-tagged images stay cached on the VPS — rolling back to a recent build needs
no pull or login. SSH into the VPS and redeploy an earlier SHA:

```bash
cd $VPS_APP_DIR
git log --oneline -10                        # find the last good commit SHA
CAMPBUDDY_TAG=<old-sha> docker compose up -d  # uses the locally cached image
```

If that image is no longer on the VPS, authenticate to GHCR first with a token
that has `read:packages`, then re-run:

```bash
echo <token> | docker login ghcr.io -u <github-username> --password-stdin
CAMPBUDDY_TAG=<old-sha> docker compose pull && CAMPBUDDY_TAG=<old-sha> docker compose up -d
```

To return to tracking `main` after fixing forward, just push the fix — the next
deploy pins to the new SHA.

---

## Security Notes

- The deploy key has SSH access to the VPS — treat the private key like a
  password and never commit it. GitHub encrypts secrets at rest and masks them in
  logs.
- CI pushes to GHCR with the built-in `GITHUB_TOKEN` (`packages: write`); no
  personal token is stored. The VPS pulls with the same token (scoped
  `packages: read`), passed over SSH for the deploy only, then logged out.
- Consider a dedicated `deploy` user on the VPS scoped to the campbuddy directory
  and Docker rather than `root`.

---

## Optional Add-Ons (not currently enabled)

- **Prevent overlapping deploys** — add to `ci.yml`:
  ```yaml
  concurrency:
    group: deploy-${{ github.ref }}
    cancel-in-progress: false
  ```
- **Manual deploy / one-click rollback** — add `workflow_dispatch` with an image
  tag input and point the deploy at it.
