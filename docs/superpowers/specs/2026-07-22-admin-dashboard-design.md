# Admin Dashboard: Role-Based Admin View

GitHub issue: [#38](https://github.com/onurburak9/campbuddy/issues/38) (sub-issue of #22)

## Problem

Phase 1 has no web UI for admin tasks — all user/scan administration goes through `cli.py` (`list-users`, `update-user`, `delete-user`, etc). We want a lightweight admin view gated by a role field on `User`, shown only to admins, instead of a separate app or section.

## Scope

- Add a boolean role flag to `User`.
- Promote/demote admins via a CLI command (no UI for this — see "Out of scope").
- Admin-only API endpoints to list all users, list all scans across users, and pause/resume/delete any user's scan.
- A frontend `/admin` page, visible only to admins, with a Users list and a cross-user Scans list (with pause/resume/delete actions).

## Out of scope

- Real-time updates, map visualization — tracked separately under #22.
- Fine-grained permission levels beyond a single admin/non-admin distinction.
- Promoting/demoting admins from the web UI — stays a CLI-only action to keep privilege escalation out of the web attack surface.
- Pagination on the admin lists, and a cross-user scan detail/results view — not needed at self-hosted scale, and not requested by the issue (list + pause/resume/delete only).

## Decisions

- **Role field**: `is_admin: bool`, default `False` — not a `role` string/enum. The scope is explicitly a single admin/non-admin distinction, and every other `User` field is a bool/string, not an enum, so a bool fits existing conventions and avoids modeling permission levels that aren't needed.
- **First admin promotion**: new `cli.py promote-admin <email> [--revoke]` command, consistent with the existing `set-password`/`update-user` CLI commands.
- **Admin UI placement**: a dedicated `/admin` route with its own sidebar icon (visible only to admins), rather than a tab bolted onto the existing Settings page — it's a distinct concern (managing other users) from personal settings.

## Data model & migration

`db/models.py`:

```python
is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Added to `User`, alongside a same-commit Alembic migration (`alembic revision --autogenerate -m "add is_admin to user"`), per `docs/agents/schema-changes.md`.

## Backend

### Service layer

`core/services/users.py`:
- `set_admin(db, email: str, is_admin: bool) -> User` — looks up by email (reusing the `NotFound` pattern from `get_user_by_email`), sets `is_admin`, flushes. Used by `cli.py promote-admin`.
- `list_users_with_scan_counts(db) -> list[tuple[User, int]]` — all non-deleted users with their active (non-deleted) scan count, via a single aggregate query (`GROUP BY Scan.user_id`) rather than N+1 per-user queries.

`core/services/scans.py`:
- Widen `get_scan`, `pause_scan`, `resume_scan`, `delete_scan` to accept `user_id: Optional[int] = None`. When `None`, the ownership filter (`Scan.user_id == user_id`) is skipped — i.e. admin scope (any user's scan). Existing call sites in `api/routes/scans.py` are unaffected since they always pass a concrete `user_id`.
- Add `list_all_scans(db) -> list[Scan]` — all non-deleted scans, `joinedload`ing `user` so callers can read the owner's email without N+1 queries.

`cli.py`:
- `promote-admin <email> [--revoke]` — calls `set_admin(db, email, not revoke)`, echoes the resulting state. Follows the confirmation-free style of `update-user` (not `delete-user`'s `--confirmation-option`, since this isn't destructive).

### API

`api/deps.py`:
```python
def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise Forbidden("Admin access required")
    return user
```
`Forbidden` is the existing `core/services/exceptions.Forbidden`, already mapped to a 403 JSON response in `api/main.py`.

`api/schemas.py`:
- `MeResponse` gains `is_admin: bool` (so the frontend learns the role right after login via `/auth/me`).
- New `AdminUserResponse`: `id`, `email`, `is_admin`, `scan_limit`, `scans_used`, `has_telegram`, `created_at`.
- New `AdminScanResponse`: `id`, `user_id`, `user_email`, `provider`, `name`, `status`, `polling_interval`, `created_at`. (A deliberately smaller shape than `ScanResponse` — the admin scans table only needs enough to identify, filter, and act on a scan; it doesn't need `search_windows`/`campsite_ids`/etc.)

`api/routes/admin.py` (new), mounted in `api/main.py` at `/api/v1/admin` with `dependencies=[Depends(get_current_admin)]` applied to the whole router:
- `GET /admin/users` → `List[AdminUserResponse]`, built from `list_users_with_scan_counts`.
- `GET /admin/scans` → `List[AdminScanResponse]`, built from `list_all_scans`.
- `POST /admin/scans/{scan_id}/pause` → `ScanResponse`, calls `scans_svc.pause_scan(db, scan_id)` (no `user_id`, i.e. admin scope).
- `POST /admin/scans/{scan_id}/resume` → `ScanResponse`, same pattern.
- `DELETE /admin/scans/{scan_id}` → `204`, same pattern via `delete_scan`.

`api/routes/auth.py`: `me()` includes `is_admin=user.is_admin` in the `MeResponse`.

## Frontend

`types/index.ts`:
- `User` gains `is_admin: boolean`.
- New `AdminUser`, `AdminScan` types mirroring the new response schemas.

`api/admin.ts` (new) + `hooks/useAdmin.ts` (new): same shape as `api/scans.ts`/`hooks/useScans.ts` — `useAdminUsers()`, `useAdminScans()`, `useAdminPauseScan()`, `useAdminResumeScan()`, `useAdminDeleteScan()` (react-query, with query invalidation on the mutations).

`hooks/queryKeys.ts`: add `adminUsers` and `adminScans` keys.

`App.tsx`: new route:
```tsx
<Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
```
`AdminPage` itself redirects to `/` if `user` is loaded and `!user.is_admin` (belt-and-suspenders — the nav icon is already hidden, and the API 403s regardless, but this avoids a blank/broken page if someone hits the URL directly).

`components/layout/IconSidebar.tsx`: new nav icon (own icon file under `public/icons/`), rendered only when `user?.is_admin`, linking to `/admin`. Follows the existing pattern of the Scans/Settings icons (active-state highlight via `pathname`).

`components/admin/AdminPage.tsx` (new): uses the existing `Tabs` component with two tabs:
- **Users tab** (`AdminUsersTab.tsx`): table — email, scans used/limit, telegram configured (✓/–), admin badge (`Badge` component), created date.
- **Scans tab** (`AdminScansTab.tsx`): table — owner email, provider, name, status (`StatusDot`), created date, actions. Pause/resume mirror the icon buttons already used elsewhere for a user's own scans; delete uses `window.confirm(...)` before calling the mutation, matching `ScanDetailHeader.tsx`'s existing delete UX.

No pagination and no cross-user scan detail/results drill-down, per "Out of scope" above.

## Testing

Per `docs/agents/testing.md` (mock all external I/O, in-memory SQLite):
- `tests/core/services/test_users.py`: `set_admin` (promote, revoke, not-found).
- `tests/core/services/test_scans.py`: widened `get_scan`/`pause_scan`/`resume_scan`/`delete_scan` with `user_id=None` (admin scope) alongside existing owner-scoped cases; `list_all_scans`.
- `tests/api/test_admin.py` (new): `get_current_admin` dependency (403 for non-admin, passes for admin) and each new route (200/204 for admin, 403 for non-admin, 404 for missing scan).
- `tests/api/test_auth.py`: `MeResponse` includes `is_admin`.
- Frontend: `AdminPage.test.tsx`, `AdminUsersTab.test.tsx`, `AdminScansTab.test.tsx`, `useAdmin.test.tsx` — mocked API responses via the existing MSW (`frontend/src/test/server.ts`) setup; `IconSidebar.test.tsx` updated to cover the icon's conditional rendering.
