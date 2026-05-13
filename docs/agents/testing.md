# Testing Guide

## Stack

- `pytest` + `pytest-mock` (already in requirements)
- Always run with the venv: `.venv/bin/pytest` or activate first

## Rules

- Mock all external I/O: camply, httpx, smtplib, requests (Telegram)
- Use in-memory SQLite for all DB tests (`sqlite:///:memory:`)
- No test may make real network calls
- Tests live in `tests/` mirroring `core/` and `db/`

## Commands

```bash
pytest tests/ -v                                              # run all tests
pytest tests/ --cov=core --cov=db --cov-report=term-missing  # with coverage
```
