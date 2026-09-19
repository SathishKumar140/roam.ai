#!/usr/bin/env bash
# Single entry point for formatting, evaluation and running RoamAI locally.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

usage() {
  cat <<'USAGE'
Usage: scripts/dev.sh <command> [args...]

  format          Format frontend/ (Prettier) and src/, tests/, evals/ (ruff)
  format:check    Check formatting for both without writing
  eval [args]     Run the LLM-judged eval suite (evals/run.py), e.g.:
                    scripts/dev.sh eval --case expense-consent
  eval:render <report.json>
                  Regenerate the HTML report from an existing JSON report
  app             Run the FastAPI application (uvicorn, auto-reload)
  frontend        Run the frontend dev server (Vite)
  hooks:install   Run format automatically on every commit (git pre-commit hook)

Python formatting requires ruff: .venv/bin/pip install -r requirements-dev.txt
USAGE
}

PY_FORMAT_PATHS=(src tests evals)

cmd="${1:-help}"
shift || true

case "$cmd" in
  format)
    (cd frontend && npm run format)
    .venv/bin/ruff format "${PY_FORMAT_PATHS[@]}"
    .venv/bin/ruff check --fix "${PY_FORMAT_PATHS[@]}"
    ;;
  format:check)
    (cd frontend && npm run format:check)
    .venv/bin/ruff format --check "${PY_FORMAT_PATHS[@]}"
    .venv/bin/ruff check "${PY_FORMAT_PATHS[@]}"
    ;;
  eval)
    .venv/bin/python -m evals.run "$@"
    ;;
  eval:render)
    .venv/bin/python -m evals.run --render "$@"
    ;;
  app)
    .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload \
      --reload-dir src --reload-dir skills --no-access-log
    ;;
  frontend)
    (cd frontend && npm run dev)
    ;;
  hooks:install)
    git config core.hooksPath .githooks
    echo "Installed: .githooks/pre-commit now formats staged files on every commit."
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage
    exit 1
    ;;
esac
