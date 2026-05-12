# VPS Deployment via GitHub Actions

Automatically redeploy CampBuddy on the VPS whenever a commit lands on `main`.

## How It Works

```
developer pushes to main
        │
        ▼
GitHub detects push event
        │
        ▼
GitHub Actions runner starts (ubuntu-latest, hosted by GitHub)
        │
        ▼
Runner SSHes into your VPS using a stored private key
        │
        ▼
Runner executes on VPS:
  git pull origin main
  docker compose build
  docker compose up -d
        │
        ▼
New containers running, old ones replaced
```

The VPS never contacts GitHub — GitHub contacts the VPS. The only requirement is that your VPS accepts SSH connections from the internet (standard port 22, or whichever port you use).

---

## Prerequisites

- A VPS with Docker and Docker Compose installed and CampBuddy already running
- SSH access to the VPS (you can already `ssh user@your-vps`)
- Admin access to the GitHub repository (to add secrets)
- `ssh-keygen` available on your local machine

---

## Step 1 — Generate a Dedicated Deploy SSH Keypair

Do this on your **local machine** (not the VPS). Using a dedicated key means you can revoke deploy access without touching your personal key.

```bash
ssh-keygen -t ed25519 -C "campbuddy-deploy" -f ~/.ssh/campbuddy_deploy
```

This creates two files:
- `~/.ssh/campbuddy_deploy` — **private key** (goes into GitHub)
- `~/.ssh/campbuddy_deploy.pub` — **public key** (goes onto the VPS)

---

## Step 2 — Authorize the Key on the VPS

Copy the public key to the VPS:

```bash
ssh-copy-id -i ~/.ssh/campbuddy_deploy.pub user@your-vps
```

Or manually append it:

```bash
cat ~/.ssh/campbuddy_deploy.pub | ssh user@your-vps "cat >> ~/.ssh/authorized_keys"
```

Verify it works before continuing:

```bash
ssh -i ~/.ssh/campbuddy_deploy user@your-vps "echo ok"
# should print: ok
```

---

## Step 3 — Add Secrets to GitHub

Go to your repository on GitHub:
**Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Secret name | Value |
|-------------|-------|
| `VPS_HOST` | Your VPS IP or hostname, e.g. `203.0.113.42` |
| `VPS_USER` | The SSH user on the VPS, e.g. `ubuntu` or `root` |
| `VPS_SSH_KEY` | The full contents of `~/.ssh/campbuddy_deploy` (the private key) |

To copy the private key contents:

```bash
cat ~/.ssh/campbuddy_deploy
```

Copy everything including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines.

---

## Step 4 — Create the GitHub Actions Workflow

Create the file `.github/workflows/deploy.yml` in the repository:

```yaml
name: Deploy to VPS

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /path/to/campbuddy
            git pull origin main
            docker compose build
            docker compose up -d
            docker system prune -f
```

Replace `/path/to/campbuddy` with the actual path on your VPS (e.g. `/home/ubuntu/campbuddy`).

The `docker system prune -f` at the end removes dangling images from previous builds, keeping disk usage in check.

---

## Step 5 — Verify It Works

1. Commit and push any small change to `main`
2. Go to your repository on GitHub → **Actions** tab
3. You should see the "Deploy to VPS" workflow running
4. Click into it to see live logs — you'll see the SSH connection, `git pull`, and Docker output
5. SSH into the VPS and confirm the containers restarted:

```bash
docker compose ps
docker compose logs --tail=20 app
```

---

## What Happens During a Deploy

The sequence on the VPS is:

1. `git pull origin main` — fetches the latest code
2. `docker compose build` — rebuilds the `app` image with the new code (uses Docker layer cache, so only changed layers rebuild)
3. `docker compose up -d` — recreates containers that have a new image; containers with no changes are left running untouched
4. `docker system prune -f` — cleans up old image layers

Total downtime is the time it takes Docker to stop the old container and start the new one — typically a few seconds.

---

## Rollback

If a bad deploy goes out, SSH into the VPS and roll back manually:

```bash
cd /path/to/campbuddy
git log --oneline -5          # find the last good commit hash
git checkout <commit-hash>    # detach to that commit
docker compose build
docker compose up -d
```

To return to tracking main after fixing the issue:

```bash
git checkout main
git pull origin main
docker compose build && docker compose up -d
```

---

## Security Notes

- The deploy key has SSH access to the VPS. Treat the private key as a password — never commit it to the repository.
- GitHub encrypts secrets at rest and never exposes them in logs.
- The key only needs to run `git pull` and `docker compose` commands. If you want to restrict it further, you can use `authorized_keys` command restrictions, but this is optional for a personal project.
- Consider creating a dedicated `deploy` user on the VPS with access only to the campbuddy directory and Docker, rather than using `root` or your personal user.
