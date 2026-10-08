# Public Landing Page — Design

**Date:** 2026-10-07
**Status:** Implemented

## Goal

Give CampBuddy a public homepage at `/` that explains how it works, where it's headed (including AI), and makes the product credible as a real company — a prerequisite for the Claude for Startups program, which requires a company email whose domain matches the company website.

## Decisions

- **Domain:** the company/umbrella domain is `maite.dev` (Maite), so a future pivot keeps the domain and email. The site is branded **CampBuddy** with a "CampBuddy is built by Maite" footer. The program application should point at `https://maite.dev` exactly and use an `@maite.dev` email.
- **Approach:** landing page lives inside the existing Vite/React SPA (no new build, deploy, or dependency). A separate static site (`maite.dev` + `app.maite.dev`) is deferred until there's a second product.
- **Routing:** `/` renders the landing page for logged-out visitors and the dashboard for logged-in users (`HomeRoute`), so existing URLs don't change. New public `/privacy` page.
- **Honesty:** CampBuddy has no LLM features today. The roadmap labels each item `Live` / `In development` / `Planned`, and the AI mockups are labelled "Concept previews · not live yet". No fabricated stats or testimonials.
- **Design language:** professional but playful, for outdoorsy technical people — topographic contour backgrounds, merit-badge SVG illustrations for the steps, monospace "live scan log" accents, a night-sky roadmap section. Fonts: Bricolage Grotesque (display) + JetBrains Mono (accents) via Google Fonts; colors reuse the existing `forest` / `campfire` / `sand` tokens plus a new `night` scale. The landing page uses its own fixed palette regardless of the dashboard's dark-mode toggle. Animations are `motion-safe` only.

## Page structure

1. Nav — logo, How it works, Roadmap, FAQ, Log in, Start a scan
2. Hero — headline, CTAs, animated scan-log card + notification toast
3. The problem — qualitative facts (months ahead / minutes / any hour)
4. How it works — 4 steps; step 4 (cart hold) is the differentiator vs alert-only competitors
5. Why CampBuddy — six feature cards, all backed by shipped features
6. Roadmap — Live: watch/alert/hold · In development: Jev-powered site judgments, Claude trip planner · Planned: LLM-scheduled scans
7. FAQ — native `<details>`
8. Final CTA + footer (Maite, `hello@maite.dev`, Privacy)

All copy lives in `frontend/src/components/landing/content.ts`.

## Testing

- Vitest: `HomeRoute` (landing vs dashboard by auth state), landing CTAs/links, roadmap status labels, footer, privacy page.
- Playwright: `e2e/landing.spec.ts` — logged-out `/`, anchor nav, CTA → `/register`, footer → `/privacy`.

## Ops checklist (manual, outside the code)

1. DNS: point `maite.dev` (A/AAAA) at the VPS; TLS on the host reverse proxy in front of the frontend container.
2. `.env`: `APP_BASE_URL=https://maite.dev`, `COOKIE_SECURE=true`.
3. Email: create `hello@maite.dev` and a personal `@maite.dev` mailbox (e.g. Cloudflare Email Routing + Gmail "send as", or Google Workspace); set `SMTP_FROM` to an `@maite.dev` address and add SPF/DKIM/DMARC records.
4. Apply at claude.com/programs/startups from a Claude Console account using the `@maite.dev` email.

### Draft "What are you building?" blurb

> Maite builds CampBuddy (maite.dev), an AI-assisted campsite assistant for the outdoors. Today it monitors Recreation.gov around the clock for cancellations, alerts users by email and Telegram, and automatically places matching sites in their cart. We're now adding Claude: a trip planner that turns a plain-language request ("4 nights in the Sierra in late July with kids") into an itinerary and the scans to secure it, plus small-model judgments that score each open site against a camper's preferences — moving toward scans that an LLM schedules on the user's behalf.

## Out of scope

Building the AI features themselves, a separate Maite company page, blog, OG image, pricing.
