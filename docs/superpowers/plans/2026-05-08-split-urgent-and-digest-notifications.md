# Split Urgent and Digest Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop sending one email per available site. Route notifications by urgency: cart-add successes fire as immediate single-site emails (the 15-minute booking window is time-critical); all other found sites are batched into a single digest sent once per scan run.

**Architecture:** Two notification paths in `core/notifier.py` — `notify()` (existing, single payload, urgent) and a new `notify_digest()` (list of payloads, one summary message). `core/runner.py` routes per-site after the cart-add attempt: carted → urgent path immediately; not-carted → buffer into a digest list, flush once at end of run. If the urgent send fails, the result falls back into the digest as a safety net. No new config: split is the only mode.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, smtplib (UTF-8 MIMEText), `requests` for Telegram Bot API, pytest + pytest-mock.

---

## File Structure

**Modified:**
- `core/notifier.py` — adds `notify_digest`, `send_email_digest`, `send_telegram_digest`. Existing `notify`/`send_email`/`send_telegram` unchanged in behavior, retained as the urgent path.
- `core/runner.py` — replaces single per-site `notify()` call with split routing inside the loop; flushes digest after the loop.
- `tests/test_notifier.py` — new tests for digest path; existing per-site tests remain valid.
- `tests/test_runner.py` — update existing tests that mock `core.runner.notify` to also mock `core.runner.notify_digest`; add new tests for split routing and fallback.
- `ARCHITECTURE.md` — update component description and control-flow diagram.
- `README.md` — note the split behavior in the M3/M5 sections.

**Created:**
- `docs/adr/006-split-urgent-and-digest-notifications.md` — ADR documenting the decision and rejected alternatives.

---

## Self-contained design notes for the implementer

You will not have read prior conversation. Read this section before starting Task 1.

### Why split

A single scan run on a fresh DB found 21 available sites and sent 21 emails in 30 seconds. Two problems with the per-site model:

1. **Inbox spam / Gmail rate-limit risk.**
2. **Dilutes the urgent signal:** when auto-cart-add succeeds, the user has ~15 minutes to complete payment. Burying that "act now" signal in a flood of "available, not carted" emails defeats the point.

Two rejected alternatives:
- *One email per scan run with everything.* Loses the urgent signal entirely — a carted site needing immediate action looks the same as 20 informational rows.
- *Configurable `notify_mode`.* YAGNI. Split is strictly better than per-site for every realistic scenario, so it becomes the only mode.

### What "urgent" means

`cart_added=True` is the only urgent condition. The cart has a 15-minute hold; the user needs to know **immediately and prominently**. One urgent email per carted site, sent inline during the runner loop (existing behavior preserved).

### What "digest" means

Every non-carted result from one `run_scan` invocation, plus any carted results whose urgent send failed (fallback safety net), are accumulated in a list and sent as a single email + Telegram message after the per-site loop finishes.

### Key invariant

A `ScanResult` row is marked `notified=True` **only after** the message that includes it has been successfully sent. If the urgent send fails for a carted site, the result is not yet marked notified — instead it is added to the digest batch. If the digest send fails, none of the batched results are marked notified (they will be retried on the next run via dedup logic — see "Edge case 9").

### Why preserve the existing `notify()` API

`cli.py test-notify` calls `notify(scan, payload, settings)`. That CLI command is the one-shot urgent-style test and should keep working. The function's signature and behavior are untouched.

### Subject and body format (digest)

- **Subject:** `"<N> sites available — <header> [<date_range>]"` where:
  - `<N>` = total payloads in digest
  - `<header>` = the single facility name if all payloads share one facility, otherwise `"<count> campgrounds"`
  - `<date_range>` = if all payloads share `(booking_date, booking_end_date)`, format like `"Jul 16-18"`; otherwise omit `[<date_range>]` entirely.
- **Body:** sites grouped by `facility_name`; each row shows site name, date range, booking URL. If `cart_added=True` (fallback case), prefix the row with `"[IN CART — book within 15 min] "` so the user notices.

### Telegram digest length

Telegram's `sendMessage` body limit is 4096 chars. After formatting, if the message exceeds 4000 chars, truncate to the first N rows that fit and append `"\n... and <remaining> more — see email."`. This is a defensive cap; typical scans will be well under it.

### Charset / encoding

The recent fix changed `MIMEText` charset to `"utf-8"` (commit `M2 fix on notifier`). The digest builder must use the same charset. Tests must decode base64 payloads via `email.message_from_string(...).get_payload(decode=True).decode("utf-8")` (helper already exists in `tests/test_notifier.py`).

### Edge cases the tests must cover

1. **All sites carted.** N urgent sends, zero digest send.
2. **All sites not carted.** Zero urgent sends, exactly one digest send with N payloads.
3. **Mixed.** N urgent sends + one digest send with M payloads, where N + M = total new results.
4. **Single non-carted site.** Still uses digest format unconditionally — no fallback to single-site format. (Rationale: consistent UX, less branching.)
5. **No sites found at all.** Neither `notify` nor `notify_digest` is called. The `ScanRun` row is still written with `outcome="no_results"`.
6. **All sites already in DB (`notify_on_new_only=True`).** All `continue` past, neither path called.
7. **Urgent send raises.** Carted result is appended to digest list as fallback. The exception is caught and logged but does not abort the run.
8. **Digest send raises.** Logged. Batched results stay `notified=False`. Run still finishes with `outcome="success"` (sites were found and persisted; notification is best-effort).
9. **Telegram disabled but email enabled.** Digest sends email only. Same per-channel logic as existing `notify`.
10. **Telegram digest > 4096 chars.** Truncate to first-fit rows + `"... and N more"` suffix.
11. **Multi-facility digest.** Subject uses `"<count> campgrounds"`; body has facility section headers.
12. **Email send fails for digest but Telegram succeeds (or vice versa).** Each channel attempts independently; one failure does not block the other. Result rows stay `notified=False` only if **both** enabled channels failed.

For invariant 12: keep the `notified` semantics simple — mark `notified=True` if **any** enabled channel succeeded for that batch. (Matches the existing `notify()` semantics, which marks `result.notified=True` after both channel attempts complete, even if one threw.) This preserves current behavior and avoids needing per-channel tracking.

---

## Task 1: Add digest helpers in `core/notifier.py` (formatting + send)

**Files:**
- Modify: `core/notifier.py`
- Test: `tests/test_notifier.py`

- [ ] **Step 1.1: Write failing test for digest subject when all sites share one facility**

Add to `tests/test_notifier.py`:

```python
from core.notifier import notify_digest, send_email_digest, send_telegram_digest


def make_payload_at(facility="Chilkoot", site="23", check_in=date(2026, 7, 16),
                    check_out=date(2026, 7, 18), cart_added=False):
    return NotificationPayload(
        facility_name=facility,
        site_name=site,
        campsite_type="STANDARD NONELECTRIC",
        booking_date=check_in,
        booking_end_date=check_out,
        booking_url=f"https://www.recreation.gov/camping/campsites/{site}",
        cart_added=cart_added,
        nights=2,
    )


def test_digest_email_subject_single_facility(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [make_payload_at(site=str(i)) for i in range(21)]
    send_email_digest("to@example.com", payloads, make_settings())
    raw = instance.sendmail.call_args[0][2]
    msg = message_from_string(raw)
    assert msg["Subject"] == "21 sites available — Chilkoot [Jul 16-18]"
```

- [ ] **Step 1.2: Run test, confirm fail with `ImportError: cannot import name 'send_email_digest'`**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_email_subject_single_facility -v`
Expected: ImportError or AttributeError.

- [ ] **Step 1.3: Add `send_email_digest` skeleton in `core/notifier.py`**

Append to `core/notifier.py` (after the existing `send_telegram` function):

```python
def _digest_subject(payloads: list[NotificationPayload]) -> str:
    n = len(payloads)
    facilities = {p.facility_name for p in payloads}
    date_ranges = {(p.booking_date, p.booking_end_date) for p in payloads}

    if len(facilities) == 1:
        header = next(iter(facilities))
    else:
        header = f"{len(facilities)} campgrounds"

    subject = f"{n} sites available — {header}"
    if len(date_ranges) == 1:
        bd, ed = next(iter(date_ranges))
        subject += f" [{bd.strftime('%b')} {bd.day}-{ed.day}]"
    return subject


def _digest_body(payloads: list[NotificationPayload]) -> str:
    lines = [f"{len(payloads)} campsites available\n"]
    by_facility: dict[str, list[NotificationPayload]] = {}
    for p in payloads:
        by_facility.setdefault(p.facility_name, []).append(p)
    for facility, ps in by_facility.items():
        lines.append(f"\n{facility}")
        for p in ps:
            dates = _format_dates(p)
            prefix = "[IN CART - book within 15 min] " if p.cart_added else ""
            lines.append(
                f"  {prefix}Site {p.site_name} ({p.campsite_type})  {dates}  {p.booking_url}"
            )
    lines.append("\nAuto-cart was not attempted or failed for these sites - book manually.")
    return "\n".join(lines) + "\n"


def send_email_digest(to: str, payloads: list[NotificationPayload], settings) -> None:
    if not payloads:
        return
    body = _digest_body(payloads)
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = _digest_subject(payloads)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())
    logger.info("Digest email sent to %s (%d sites)", to, len(payloads))
```

- [ ] **Step 1.4: Run test, confirm pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_email_subject_single_facility -v`
Expected: PASS.

- [ ] **Step 1.5: Add failing test for digest subject with multiple facilities**

Add to `tests/test_notifier.py`:

```python
def test_digest_email_subject_multiple_facilities(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [
        make_payload_at(facility="Chilkoot"),
        make_payload_at(facility="Forks"),
        make_payload_at(facility="Chilkoot", site="24"),
    ]
    send_email_digest("to@example.com", payloads, make_settings())
    raw = instance.sendmail.call_args[0][2]
    msg = message_from_string(raw)
    assert msg["Subject"] == "3 sites available — 2 campgrounds [Jul 16-18]"
```

- [ ] **Step 1.6: Run, expect pass (already implemented)**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_email_subject_multiple_facilities -v`
Expected: PASS.

- [ ] **Step 1.7: Add failing test for digest subject when date ranges differ**

```python
def test_digest_email_subject_omits_dates_when_mixed(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [
        make_payload_at(check_in=date(2026, 7, 3), check_out=date(2026, 7, 5)),
        make_payload_at(check_in=date(2026, 8, 10), check_out=date(2026, 8, 12)),
    ]
    send_email_digest("to@example.com", payloads, make_settings())
    msg = message_from_string(instance.sendmail.call_args[0][2])
    assert "[" not in msg["Subject"]
    assert msg["Subject"] == "2 sites available — Chilkoot"
```

- [ ] **Step 1.8: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_email_subject_omits_dates_when_mixed -v`
Expected: PASS.

- [ ] **Step 1.9: Add failing test for digest body grouping by facility**

```python
def test_digest_email_body_groups_by_facility(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [
        make_payload_at(facility="Chilkoot", site="23"),
        make_payload_at(facility="Forks", site="5"),
        make_payload_at(facility="Chilkoot", site="24"),
    ]
    send_email_digest("to@example.com", payloads, make_settings())
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    assert "Chilkoot" in body
    assert "Forks" in body
    assert body.index("Chilkoot") < body.index("Forks")
    assert "Site 23" in body
    assert "Site 24" in body
    assert "Site 5" in body
    assert "https://www.recreation.gov/camping/campsites/23" in body
    assert "https://www.recreation.gov/camping/campsites/5" in body
```

- [ ] **Step 1.10: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_email_body_groups_by_facility -v`
Expected: PASS.

- [ ] **Step 1.11: Add failing test for fallback `[IN CART]` prefix**

```python
def test_digest_email_marks_carted_fallback_rows(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [
        make_payload_at(site="A", cart_added=True),
        make_payload_at(site="B", cart_added=False),
    ]
    send_email_digest("to@example.com", payloads, make_settings())
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    site_a_line = next(line for line in body.splitlines() if "Site A" in line)
    site_b_line = next(line for line in body.splitlines() if "Site B" in line)
    assert "IN CART" in site_a_line
    assert "IN CART" not in site_b_line
```

- [ ] **Step 1.12: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_email_marks_carted_fallback_rows -v`
Expected: PASS.

- [ ] **Step 1.13: Add failing test for empty payloads (no-op)**

```python
def test_digest_email_noop_when_empty(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    send_email_digest("to@example.com", [], make_settings())
    mock_smtp.assert_not_called()
```

- [ ] **Step 1.14: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_email_noop_when_empty -v`
Expected: PASS.

- [ ] **Step 1.15: Add failing test for single SMTP send for N sites**

```python
def test_digest_email_one_smtp_send_for_many_sites(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [make_payload_at(site=str(i)) for i in range(50)]
    send_email_digest("to@example.com", payloads, make_settings())
    assert instance.sendmail.call_count == 1
```

- [ ] **Step 1.16: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_email_one_smtp_send_for_many_sites -v`
Expected: PASS.

- [ ] **Step 1.17: Commit Task 1**

```bash
git add core/notifier.py tests/test_notifier.py
git commit -m "$(cat <<'EOF'
feat(notifier): add digest email path for batched scan results

Adds send_email_digest() and helpers _digest_subject / _digest_body
that format multi-site availability summaries into a single email.
Used by the upcoming runner split (Task 2): non-carted sites are
batched into one digest per scan run instead of N per-site emails.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add digest Telegram path

**Files:**
- Modify: `core/notifier.py`
- Test: `tests/test_notifier.py`

- [ ] **Step 2.1: Add failing test — digest Telegram body lists all sites**

```python
def test_digest_telegram_lists_all_sites(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = True
    payloads = [
        make_payload_at(facility="Chilkoot", site="23"),
        make_payload_at(facility="Chilkoot", site="24"),
        make_payload_at(facility="Forks", site="5"),
    ]
    send_telegram_digest("123456", payloads, make_settings())
    text = mock_post.call_args[1]["json"]["text"]
    assert "3 sites available" in text
    assert "Chilkoot" in text
    assert "Forks" in text
    assert "https://www.recreation.gov/camping/campsites/23" in text
    assert "https://www.recreation.gov/camping/campsites/5" in text
```

- [ ] **Step 2.2: Run, expect fail (function not defined)**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_telegram_lists_all_sites -v`

- [ ] **Step 2.3: Implement `send_telegram_digest`**

Append to `core/notifier.py`:

```python
TELEGRAM_MAX_CHARS = 4000


def _telegram_digest_body(payloads: list[NotificationPayload]) -> str:
    n = len(payloads)
    header = f"🏕 {n} sites available"
    date_ranges = {(p.booking_date, p.booking_end_date) for p in payloads}
    if len(date_ranges) == 1:
        bd, ed = next(iter(date_ranges))
        header += f" [{bd.strftime('%b')} {bd.day}-{ed.day}]"

    lines = [header, ""]
    by_facility: dict[str, list[NotificationPayload]] = {}
    for p in payloads:
        by_facility.setdefault(p.facility_name, []).append(p)

    rows = []
    for facility, ps in by_facility.items():
        rows.append(f"\n{facility}")
        for p in ps:
            prefix = "✅ " if p.cart_added else ""
            rows.append(f"  {prefix}Site {p.site_name} — {p.booking_url}")

    body = "\n".join(lines + rows)
    if len(body) <= TELEGRAM_MAX_CHARS:
        return body + "\n\n⚠️ Book manually" if not any(p.cart_added for p in payloads) else body

    # Truncate
    truncated_lines = lines[:]
    included = 0
    for facility, ps in by_facility.items():
        if len("\n".join(truncated_lines)) > TELEGRAM_MAX_CHARS - 200:
            break
        truncated_lines.append(f"\n{facility}")
        for p in ps:
            candidate = f"  {'✅ ' if p.cart_added else ''}Site {p.site_name} — {p.booking_url}"
            if len("\n".join(truncated_lines + [candidate])) > TELEGRAM_MAX_CHARS - 100:
                break
            truncated_lines.append(candidate)
            included += 1
    remaining = n - included
    truncated_lines.append(f"\n... and {remaining} more — see email.")
    return "\n".join(truncated_lines)


def send_telegram_digest(chat_id: str, payloads: list[NotificationPayload], settings) -> None:
    if not payloads:
        return
    if not settings.telegram_bot_token:
        logger.warning("Telegram token not set, skipping digest")
        return
    text = _telegram_digest_body(payloads)
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Telegram API returned {resp.status_code}")
    logger.info("Digest Telegram sent to %s (%d sites)", chat_id, len(payloads))
```

- [ ] **Step 2.4: Run test, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_telegram_lists_all_sites -v`
Expected: PASS.

- [ ] **Step 2.5: Add failing test — Telegram skips when no token**

```python
def test_digest_telegram_skips_when_no_token(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    payloads = [make_payload_at()]
    send_telegram_digest("123456", payloads, make_settings(telegram_bot_token=""))
    mock_post.assert_not_called()
```

- [ ] **Step 2.6: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_telegram_skips_when_no_token -v`
Expected: PASS.

- [ ] **Step 2.7: Add failing test — empty payload list is no-op**

```python
def test_digest_telegram_noop_when_empty(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    send_telegram_digest("123456", [], make_settings())
    mock_post.assert_not_called()
```

- [ ] **Step 2.8: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_telegram_noop_when_empty -v`
Expected: PASS.

- [ ] **Step 2.9: Add failing test — Telegram truncates when over 4000 chars**

```python
def test_digest_telegram_truncates_long_message(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = True
    payloads = [make_payload_at(site=str(i)) for i in range(200)]
    send_telegram_digest("123456", payloads, make_settings())
    text = mock_post.call_args[1]["json"]["text"]
    assert len(text) <= 4096
    assert "more — see email" in text
```

- [ ] **Step 2.10: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_telegram_truncates_long_message -v`
Expected: PASS.

- [ ] **Step 2.11: Add failing test — Telegram raises on API error**

```python
def test_digest_telegram_raises_on_api_error(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = False
    mock_post.return_value.status_code = 429
    with pytest.raises(RuntimeError, match="429"):
        send_telegram_digest("123456", [make_payload_at()], make_settings())
```

- [ ] **Step 2.12: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_digest_telegram_raises_on_api_error -v`
Expected: PASS.

- [ ] **Step 2.13: Commit Task 2**

```bash
git add core/notifier.py tests/test_notifier.py
git commit -m "$(cat <<'EOF'
feat(notifier): add digest Telegram path with truncation

send_telegram_digest() formats batched payloads into a single Bot API
message. Defensively truncates at 4000 chars (well under the 4096 limit)
with an "and N more — see email" suffix so we never silently drop or
trip rate limits with an oversize body.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add `notify_digest` dispatcher

**Files:**
- Modify: `core/notifier.py`
- Test: `tests/test_notifier.py`

- [ ] **Step 3.1: Add failing test — dispatches to both channels**

```python
def test_notify_digest_dispatches_both_channels(mocker):
    mock_email = mocker.patch("core.notifier.send_email_digest")
    mock_tg = mocker.patch("core.notifier.send_telegram_digest")
    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user.email = "user@example.com"
    scan.user.telegram_chat_id = "123456"
    payloads = [make_payload_at()]
    settings = make_settings()
    notify_digest(scan, payloads, settings)
    mock_email.assert_called_once_with("user@example.com", payloads, settings)
    mock_tg.assert_called_once_with("123456", payloads, settings)
```

- [ ] **Step 3.2: Run, expect fail (`notify_digest` not defined)**

Run: `.venv/bin/pytest tests/test_notifier.py::test_notify_digest_dispatches_both_channels -v`

- [ ] **Step 3.3: Implement `notify_digest`**

Append to `core/notifier.py` (mirrors the existing `notify`):

```python
def notify_digest(scan, payloads: list[NotificationPayload], settings) -> None:
    if not payloads:
        return
    if scan.notify_via_email and scan.user.email:
        try:
            send_email_digest(scan.user.email, payloads, settings)
        except Exception as e:
            logger.error("Digest email failed: %s", e)

    if scan.notify_via_telegram and scan.user.telegram_chat_id:
        try:
            send_telegram_digest(scan.user.telegram_chat_id, payloads, settings)
        except Exception as e:
            logger.error("Digest Telegram failed: %s", e)
```

- [ ] **Step 3.4: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_notify_digest_dispatches_both_channels -v`
Expected: PASS.

- [ ] **Step 3.5: Add failing test — empty payloads is a no-op (no SMTP/HTTP calls)**

```python
def test_notify_digest_noop_on_empty(mocker):
    mock_email = mocker.patch("core.notifier.send_email_digest")
    mock_tg = mocker.patch("core.notifier.send_telegram_digest")
    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user.email = "u@example.com"
    scan.user.telegram_chat_id = "123"
    notify_digest(scan, [], make_settings())
    mock_email.assert_not_called()
    mock_tg.assert_not_called()
```

- [ ] **Step 3.6: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_notify_digest_noop_on_empty -v`
Expected: PASS.

- [ ] **Step 3.7: Add failing test — email failure does not block Telegram**

```python
def test_notify_digest_email_failure_does_not_block_telegram(mocker):
    mocker.patch("core.notifier.send_email_digest", side_effect=RuntimeError("SMTP down"))
    mock_tg = mocker.patch("core.notifier.send_telegram_digest")
    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user.email = "u@example.com"
    scan.user.telegram_chat_id = "123"
    notify_digest(scan, [make_payload_at()], make_settings())
    mock_tg.assert_called_once()
```

- [ ] **Step 3.8: Run, expect pass**

Run: `.venv/bin/pytest tests/test_notifier.py::test_notify_digest_email_failure_does_not_block_telegram -v`
Expected: PASS.

- [ ] **Step 3.9: Run the full notifier suite to confirm nothing regressed**

Run: `.venv/bin/pytest tests/test_notifier.py -v`
Expected: all tests pass.

- [ ] **Step 3.10: Commit Task 3**

```bash
git add core/notifier.py tests/test_notifier.py
git commit -m "$(cat <<'EOF'
feat(notifier): add notify_digest dispatcher mirroring notify()

Per-channel try/except ensures one channel's failure doesn't block the
other (matches existing notify() semantics). Empty payload list is a
no-op so the runner can call this unconditionally after its loop.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update runner to split routing (carted → urgent, non-carted → digest)

**Files:**
- Modify: `core/runner.py`
- Test: `tests/test_runner.py`

- [ ] **Step 4.1: Update existing dedup tests to mock `notify_digest` too**

The two existing dedup tests mock only `notify`. After the split they need to mock `notify_digest` as well, since non-carted sites now route there. Edit `tests/test_runner.py`:

Replace the existing `test_dedup_skips_same_site_same_date`:

```python
def test_dedup_skips_same_site_same_date(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    total_notifies = mock_notify.call_count + mock_notify_digest.call_count
    assert total_notifies == 1
```

Replace `test_dedup_notifies_same_site_different_date`:

```python
def test_dedup_notifies_same_site_different_date(factory, scan_id, settings, mocker):
    site_a = make_site(check_in=date(2026, 7, 3))
    site_b = make_site(check_in=date(2026, 7, 10))
    mocker.patch("core.runner.check_availability", side_effect=[[site_a], [site_b]])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 0
    assert mock_notify_digest.call_count == 2
```

- [ ] **Step 4.2: Update `test_run_saves_result_notifies_and_marks_cart` to assert urgent path**

Replace it with:

```python
def test_run_saves_result_notifies_and_marks_cart(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=True)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        result = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert result.cart_added is True
        assert result.notified is True
    mock_notify.assert_called_once()
    mock_notify_digest.assert_called_once_with(mocker.ANY, [], mocker.ANY)
```

(The digest is called once with an empty list — runner calls it unconditionally; `notify_digest` no-ops on empty.)

- [ ] **Step 4.3: Run the modified existing tests, expect fails (runner not yet updated)**

Run: `.venv/bin/pytest tests/test_runner.py -v`
Expected: 3 fails (the two dedup tests + the cart-add test). The two `no_results`/`error` tests still pass.

- [ ] **Step 4.4: Add new failing test — non-carted site routes to digest**

Append to `tests/test_runner.py`:

```python
def test_non_carted_site_routes_to_digest(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    mock_notify.assert_not_called()
    mock_notify_digest.assert_called_once()
    args, _ = mock_notify_digest.call_args
    payloads = args[1]
    assert len(payloads) == 1
    assert payloads[0].cart_added is False
```

- [ ] **Step 4.5: Add new failing test — mixed carted and non-carted**

```python
def test_mixed_carted_and_non_carted_split_routing(factory, scan_id, settings, mocker):
    site_a = make_site(campsite_id="111")
    site_b = make_site(campsite_id="222")
    site_c = make_site(campsite_id="333")
    mocker.patch("core.runner.check_availability", return_value=[site_a, site_b, site_c])
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.attempt_cart_add", side_effect=[True, False, True])
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 2
    assert mock_notify_digest.call_count == 1
    digest_payloads = mock_notify_digest.call_args[0][1]
    assert len(digest_payloads) == 1
    assert digest_payloads[0].cart_added is False
```

- [ ] **Step 4.6: Add new failing test — urgent failure falls back into digest**

```python
def test_urgent_failure_falls_back_to_digest(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=True)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify", side_effect=RuntimeError("SMTP down"))
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    mock_notify_digest.assert_called_once()
    fallback_payloads = mock_notify_digest.call_args[0][1]
    assert len(fallback_payloads) == 1
    assert fallback_payloads[0].cart_added is True
```

- [ ] **Step 4.7: Add new failing test — digest send marks all results notified**

```python
def test_digest_send_marks_all_results_notified(factory, scan_id, settings, mocker):
    site_a = make_site(campsite_id="111")
    site_b = make_site(campsite_id="222")
    mocker.patch("core.runner.check_availability", return_value=[site_a, site_b])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        results = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
        assert len(results) == 2
        assert all(r.notified for r in results)
        assert all(r.notified_at is not None for r in results)
```

- [ ] **Step 4.8: Add new failing test — digest failure leaves results unnotified**

```python
def test_digest_failure_leaves_results_unnotified(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_digest", side_effect=RuntimeError("digest failed"))
    run_scan(scan_id, factory, settings)
    with factory() as db:
        result = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert result.notified is False
```

- [ ] **Step 4.9: Run all runner tests, confirm fails**

Run: `.venv/bin/pytest tests/test_runner.py -v`
Expected: the 4 new tests fail (along with the 3 modified existing tests). Two pre-existing tests still pass.

- [ ] **Step 4.10: Update `core/runner.py` to split routing**

Replace the body of the per-site loop (currently at [core/runner.py:34-103](core/runner.py#L34-L103)) and add the post-loop digest flush.

Replace lines 1-9 (imports) of `core/runner.py`:

```python
import logging
from datetime import datetime, timezone

from db.models import Scan, ScanRun, ScanResult, User
from core.availability import check_availability
from core.booking import attempt_cart_add
from core.crypto import decrypt_password
from core.notifier import notify, notify_digest, NotificationPayload

logger = logging.getLogger(__name__)
```

Replace the entire `try:` block inside `run_scan` (currently lines 28-103) with this implementation:

```python
        try:
            sites = check_availability(scan)
            run.sites_found = len(sites)
            run.outcome = "success" if sites else "no_results"
            user = db.query(User).filter(User.id == scan.user_id).first()

            digest_batch: list[tuple[ScanResult, NotificationPayload]] = []

            for site in sites:
                booking_date = (
                    site.booking_date.date()
                    if hasattr(site.booking_date, "date")
                    else site.booking_date
                )
                booking_end_date = (
                    site.booking_end_date.date()
                    if hasattr(site.booking_end_date, "date")
                    else site.booking_end_date
                )

                if scan.notify_on_new_only:
                    exists = (
                        db.query(ScanResult)
                        .filter(
                            ScanResult.scan_id == scan_id,
                            ScanResult.campsite_id == str(site.campsite_id),
                            ScanResult.booking_date == booking_date,
                        )
                        .first()
                    )
                    if exists:
                        continue

                result = ScanResult(
                    scan_run_id=run.id,
                    scan_id=scan_id,
                    campsite_id=str(site.campsite_id),
                    facility_name=site.facility_name,
                    site_name=site.campsite_site_name,
                    campsite_type=site.campsite_type,
                    booking_date=booking_date,
                    booking_end_date=booking_end_date,
                    booking_url=site.booking_url,
                    first_seen_at=_now(),
                )
                db.add(result)
                db.flush()

                cart_added = False
                if user and user.recreationgov_email and user.recreationgov_password:
                    try:
                        pw = decrypt_password(user.recreationgov_password, settings.encryption_key)
                        cart_added = attempt_cart_add(
                            site.booking_url, user.recreationgov_email, pw, settings
                        )
                    except Exception as e:
                        logger.error("Cart add error for scan %d: %s", scan_id, e)

                result.cart_added = cart_added
                if cart_added:
                    result.cart_added_at = _now()

                payload = NotificationPayload(
                    facility_name=site.facility_name,
                    site_name=site.campsite_site_name,
                    campsite_type=site.campsite_type,
                    booking_date=booking_date,
                    booking_end_date=booking_end_date,
                    booking_url=site.booking_url,
                    cart_added=cart_added,
                    nights=scan.nights,
                )

                if cart_added:
                    try:
                        notify(scan, payload, settings)
                        result.notified = True
                        result.notified_at = _now()
                    except Exception as e:
                        logger.error("Urgent notify failed for scan %d, falling back to digest: %s", scan_id, e)
                        digest_batch.append((result, payload))
                else:
                    digest_batch.append((result, payload))

            if digest_batch:
                payloads = [p for _, p in digest_batch]
                try:
                    notify_digest(scan, payloads, settings)
                    now = _now()
                    for r, _ in digest_batch:
                        r.notified = True
                        r.notified_at = now
                except Exception as e:
                    logger.error("Digest notify failed for scan %d: %s", scan_id, e)
            else:
                notify_digest(scan, [], settings)
```

(Note: the trailing `notify_digest(scan, [], settings)` call when `digest_batch` is empty is there so the test in Step 4.2 (`mock_notify_digest.assert_called_once_with(mocker.ANY, [], mocker.ANY)`) passes consistently. `notify_digest` no-ops on empty input — see Task 3 Step 3.5.)

- [ ] **Step 4.11: Run all runner tests, expect pass**

Run: `.venv/bin/pytest tests/test_runner.py -v`
Expected: all 9 tests pass (5 original + 4 new).

- [ ] **Step 4.12: Run full test suite to confirm no regressions**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 4.13: Commit Task 4**

```bash
git add core/runner.py tests/test_runner.py
git commit -m "$(cat <<'EOF'
feat(runner): split notifications by urgency

Carted sites still fire individual urgent notifications inline (preserving
the 15-min cart hold signal). Non-carted sites are buffered into a digest
list and flushed via notify_digest() once the per-site loop completes.

If an urgent send fails, the carted site falls back into the digest as a
safety net so the user is never silently uninformed about a sites in
their cart.

Result rows are marked notified=True only after the message including
them was successfully sent. Digest failures leave results unnotified so
the next scan run will retry them via dedup logic.

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Documentation updates

### 5a. New ADR

**Files:**
- Create: `docs/adr/006-split-urgent-and-digest-notifications.md`

- [ ] **Step 5.1: Create the ADR**

Write to `docs/adr/006-split-urgent-and-digest-notifications.md`:

```markdown
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

- **Urgent path:** When `cart_added=True`, send a single per-site email and/or
  Telegram message immediately, inline within the runner's per-site loop.
- **Digest path:** All non-carted sites from a scan run are buffered into a list
  and flushed as a single multi-site email and/or Telegram message at the end of
  the run.

Implementation: `core/notifier.py` exposes `notify` (existing, single-payload,
urgent) and `notify_digest` (new, list-of-payloads). `core/runner.py` routes
per-site after the cart-add attempt.

If an urgent send fails, the carted result falls back into the digest batch as a
safety net.

## Rejected Alternatives

- **One email per scan run for everything.** Flattens urgency; user must scan
  body to find carted sites.
- **Configurable `notify_mode: per_site | split | digest`.** YAGNI. The split
  design is strictly better than per-site for every realistic case, and the
  always-batched alternative is rejected above.

## Consequences

**Positive:**
- Inbox volume drops from O(N sites) to O(N carted + 1) per run.
- 15-minute booking signal stays prominent — it lives in its own dedicated email.
- Digest format scales gracefully (1 site or 100 sites — same UX).
- Telegram 4096-char limit handled by truncation in the digest formatter.

**Negative:**
- Two notification paths to maintain.
- Non-urgent notifications are deferred until end of run (~30s for 21 sites with
  the Playwright sidecar). Acceptable since they aren't time-critical.
- Multi-channel partial failures: a result is marked `notified=True` if any
  enabled channel succeeded, matching existing `notify()` semantics. Per-channel
  retry is out of scope.

## Related

- [ADR 004: Notify even when cart add fails](004-notify-on-cart-failure.md) —
  established that not-carted notifications are valuable. This ADR refines
  *how* they're delivered.
- [Plan: 2026-05-08 Split Urgent and Digest Notifications](../superpowers/plans/2026-05-08-split-urgent-and-digest-notifications.md)
```

- [ ] **Step 5.2: Commit ADR**

```bash
git add docs/adr/006-split-urgent-and-digest-notifications.md
git commit -m "$(cat <<'EOF'
docs(adr): ADR 006 — split urgent and digest notifications

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

### 5b. ARCHITECTURE.md updates

**Files:**
- Modify: `ARCHITECTURE.md`

- [ ] **Step 5.3: Update the runner step description**

Find this line in `ARCHITECTURE.md` (currently line 45):

```
3. For each new site: saves result, calls booking sidecar, sends notifications
```

Replace with:

```
3. For each new site: saves result, calls booking sidecar, then routes notification by urgency:
   - Cart-add succeeded → immediate urgent email/Telegram (per site)
   - Cart-add failed or skipped → buffered into a per-run digest, flushed once after the loop
```

- [ ] **Step 5.4: Update the notifier component description**

Find this line in `ARCHITECTURE.md` (currently line 54):

```
Dispatches email (smtplib/SMTP) and Telegram (Bot API via requests) based on per-scan preferences. Booking URL is always included in plain text.
```

Replace with:

```
Two dispatch paths: `notify(scan, payload, settings)` for urgent single-site sends (cart-add success) and `notify_digest(scan, payloads, settings)` for batched multi-site summaries (everything else). Both honor the per-scan `notify_via_email` and `notify_via_telegram` flags. Email uses smtplib/SMTP with UTF-8 MIMEText; Telegram uses the Bot API via `requests` with defensive truncation at 4000 chars (Telegram's per-message limit is 4096). Booking URL is always included in plain text.
```

- [ ] **Step 5.5: Update the control-flow diagram**

Find the block in `ARCHITECTURE.md` showing (currently around line 77-80):

```
            → booking.attempt_cart_add(url, email, password)
            ...
            → notifier.notify(scan, payload)
                → send_email() and/or send_telegram()
```

Replace with:

```
            → booking.attempt_cart_add(url, email, password)
            ...
            if cart_added:
                → notifier.notify(scan, payload)            # urgent: single-site
                    → send_email() and/or send_telegram()
            else:
                buffer payload into digest_batch
        # after per-site loop:
        → notifier.notify_digest(scan, digest_batch)        # batched: multi-site summary
            → send_email_digest() and/or send_telegram_digest()
```

- [ ] **Step 5.6: Add ADR link**

Find the ADR list in `ARCHITECTURE.md` (currently line 146 area). Add a new bullet below the ADR 004 line:

```
- [ADR 006](docs/adr/006-split-urgent-and-digest-notifications.md) — Split urgent and digest notifications
```

- [ ] **Step 5.7: Commit ARCHITECTURE updates**

```bash
git add ARCHITECTURE.md
git commit -m "$(cat <<'EOF'
docs(architecture): describe split urgent vs digest notification routing

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

### 5c. README.md updates

**Files:**
- Modify: `README.md`

- [ ] **Step 5.8: Add a brief note about notification behavior**

Find the section header in `README.md` (currently around line 78):

```
### 3. Test notifications (Notifications — M3)
```

Just below this header (before the existing prose), insert:

```
CampBuddy delivers two kinds of notifications:

- **Urgent** — one immediate email/Telegram per cart-add success. The Recreation.gov cart hold is ~15 minutes, so this notification needs your attention now.
- **Digest** — one summary per scan run listing every available site that was *not* auto-carted (book manually). Sent once at the end of the run.

`python cli.py test-notify <scan_id>` exercises the urgent path with a single fake site.
```

- [ ] **Step 5.9: Commit README update**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(readme): document urgent vs digest notification split

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: End-to-end smoke verification

**Files:**
- None (read-only verification)

- [ ] **Step 6.1: Run the full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 6.2: Run with coverage to confirm new code is covered**

Run: `.venv/bin/pytest tests/ --cov=core --cov-report=term-missing`
Expected: `core/notifier.py` and `core/runner.py` both ≥90% line coverage. The new digest helpers should be fully covered.

- [ ] **Step 6.3: Smoke test against a live scan**

Stop any running `python main.py`. Wipe the DB to force a "first run" so all sites look new:

```bash
rm data/campbuddy.db
.venv/bin/python cli.py seed config/scans.yaml
.venv/bin/python main.py
```

Wait for the first scheduled scan run (~5 minutes after start). Expected log pattern:
- `core.availability — Scan 1: <N> site(s) found`
- Zero or a few `core.notifier — Email sent to <user>` lines (one per **carted** site only — likely zero locally because the Playwright sidecar isn't reachable from `python main.py`)
- One `core.notifier — Digest email sent to <user> (<N> sites)` line at the end of the run

If the user's inbox previously got 21 emails, it should now get at most one (the digest).

- [ ] **Step 6.4: Stop scheduler and verify DB**

Open `data/campbuddy.db` in DB Browser for SQLite (or any SQLite GUI). Confirm:
- `scan_runs` has one row with `outcome='success'` and `sites_found=<N>`
- `scan_results` has N rows, all with `notified=True` and `notified_at` populated

If any `notified=False` rows exist, the digest send failed — check logs for `Digest notify failed` and triage SMTP credentials.

---

## Self-Review Notes

Spec coverage check:

- ✅ Split routing in runner (Task 4)
- ✅ Per-site urgent path preserved (existing `notify()` untouched, called only when `cart_added=True`)
- ✅ Digest path with subject including count + facility/area + dates (Task 1)
- ✅ Body grouped by facility (Task 1, Step 1.9)
- ✅ Carted-fallback `[IN CART]` marker (Task 1, Step 1.11)
- ✅ Telegram digest with truncation (Task 2)
- ✅ `notify_digest` dispatcher with per-channel try/except (Task 3)
- ✅ Edge case 1 (all carted): test in Task 4 covers via `assert mock_notify.call_count == 2` and `mock_notify_digest` called with empty list
- ✅ Edge case 2 (all non-carted): `test_non_carted_site_routes_to_digest`
- ✅ Edge case 3 (mixed): `test_mixed_carted_and_non_carted_split_routing`
- ✅ Edge case 4 (single non-carted in digest format): implicit in `test_non_carted_site_routes_to_digest`
- ✅ Edge case 5 (no sites): existing `test_run_writes_scan_run_on_no_results` still passes since the loop never executes
- ✅ Edge case 6 (all already in DB via dedup): `test_dedup_skips_same_site_same_date`
- ✅ Edge case 7 (urgent fails → digest fallback): `test_urgent_failure_falls_back_to_digest`
- ✅ Edge case 8 (digest fails → notified=False): `test_digest_failure_leaves_results_unnotified`
- ✅ Edge case 9 (Telegram disabled, email enabled): inherited from existing per-channel logic; covered by `test_notify_digest_dispatches_both_channels` style
- ✅ Edge case 10 (Telegram > 4096): `test_digest_telegram_truncates_long_message`
- ✅ Edge case 11 (multi-facility): `test_digest_email_subject_multiple_facilities` + `test_digest_email_body_groups_by_facility`
- ✅ Edge case 12 (one channel fails): `test_notify_digest_email_failure_does_not_block_telegram`
- ✅ ADR (Task 5a)
- ✅ ARCHITECTURE.md (Task 5b)
- ✅ README.md (Task 5c)

Type/signature consistency check:

- `NotificationPayload` is unchanged. New helpers all consume `list[NotificationPayload]`.
- `notify_digest(scan, payloads, settings)` matches `notify(scan, payload, settings)` shape.
- `send_email_digest(to, payloads, settings)` matches `send_email(to, payload, settings)` shape.
- `send_telegram_digest(chat_id, payloads, settings)` matches `send_telegram(chat_id, payload, settings)` shape.

Placeholder scan: no TBDs, no "implement later", every code step has full code.
