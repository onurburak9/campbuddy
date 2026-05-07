# ADR 005: pydantic v1 (driven by camply constraint)

**Date:** 2026-05-07  
**Status:** Accepted

## Context
camply 0.34.1 (chosen in ADR 001) declares `pydantic~=1.10` as a hard dependency. The latest pydantic is v2.x, and the `pydantic-settings` package only exists for pydantic v2. We needed a settings library for `config/settings.py`.

## Decision
Pin `pydantic==1.10.22` explicitly in `requirements.txt`. Use pydantic v1's built-in `BaseSettings` (`from pydantic import BaseSettings`) instead of the separate `pydantic-settings` package. Run the project inside a project-local `.venv` to keep this isolated from a developer's global pydantic v2 install.

## Consequences
- All settings code uses pydantic v1 syntax: inner `class Config:` instead of `model_config = SettingsConfigDict(...)`, `@validator` instead of `@field_validator`
- Developers must `python -m venv .venv && pip install -r requirements.txt` and use the venv — global pydantic v2 will silently break camply imports
- `.venv/` is in `.gitignore`
- Docker container builds its own clean Python environment, so production is unaffected
- If camply later releases a pydantic v2-compatible version, this ADR can be revisited
