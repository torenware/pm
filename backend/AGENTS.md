# Backend instructions

## Purpose

This directory contains the FastAPI application that serves the API and browser application.

## Current structure

- `app/main.py` creates the FastAPI application, exposes `/api/health`, and serves the static frontend at `/`.
- `app/auth.py` owns signed, expiring in-memory sessions and the reusable authenticated-route dependency.
- `app/static/` is replaced by the exported Next.js application during the Docker build. Its checked-in page remains a lightweight fallback for direct backend development.
- `tests/` contains backend tests using FastAPI's TestClient.
- `pyproject.toml` and `uv.lock` define the Python 3.12 project and dependencies managed by `uv`.

## Commands

- `uv run pytest`: run backend tests.
- `uv run uvicorn app.main:app --reload`: run the backend directly for development.

## Guidelines

- Keep API routes under `/api` so browser routes remain available to the static frontend.
- Register API routes before mounting the frontend at `/`.
- Keep session identifiers in signed HTTP-only cookies and credentials out of responses and logs.
- Keep application data under `/data` in the container so it persists in the repository-local `data/` directory.
- Add focused tests for each endpoint and backend behavior.
- Do not expose values from the root `.env` file through API responses or logs.