#!/usr/bin/env bash
# Single entry point for formatting, evaluation and running RoamAI locally.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

usage() {
  cat <<'USAGE'
Usage: scripts/dev.sh <command> [args...]

  all [port]      Run everything together: backend, frontend, and Telegram tunnel
                  (default port: 8000; aliases: dev, start)
                  - Backend FastAPI/Uvicorn on http://127.0.0.1:8000
                  - Frontend simulator on http://localhost:5173
                  - Cloudflare tunnel + automatic Telegram webhook registration
  app [port]      Run the FastAPI application (uvicorn, auto-reload)
  frontend        Run the frontend dev server (Vite)
  tunnel [port]   Run Cloudflare tunnel to expose local backend for Telegram webhook
                  (alias: telegram:tunnel, tunnel:telegram)
  telegram:webhook <tunnel-url>
                  Register Telegram webhook with secret token from .env
  telegram:info   Check current Telegram webhook status
  format          Format frontend/ (Prettier) and src/, tests/, evals/ (ruff)
  format:check    Check formatting for both without writing
  eval [args]     Run the LLM-judged eval suite (evals/run.py), e.g.:
                    scripts/dev.sh eval --case expense-consent
  eval:render <report.json>
                  Regenerate the HTML report from an existing JSON report
  hooks:install   Run format automatically on every commit (git pre-commit hook)

Python formatting requires ruff: .venv/bin/pip install -r requirements-dev.txt
USAGE
}

# Prepend standard tool directories to PATH if present
for dir in /opt/homebrew/bin /usr/local/bin; do
  if [ -d "$dir" ] && [[ ":$PATH:" != *":$dir:"* ]]; then
    PATH="$dir:$PATH"
  fi
done

# If npm/node not yet found, check nvm default version
if ! command -v npm >/dev/null 2>&1 && [ -d "${HOME}/.nvm/versions/node" ]; then
  LATEST_NODE="$(ls -d "${HOME}/.nvm/versions/node"/* 2>/dev/null | tail -n 1)/bin"
  if [ -d "$LATEST_NODE" ]; then
    PATH="$LATEST_NODE:$PATH"
  fi
fi
export PATH

get_env_val() {
  local key="$1"
  if [ -f .env ]; then
    grep -E "^${key}=" .env | head -n 1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" | tr -d '\r' || true
  fi
}

find_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    command -v cloudflared
  elif [ -x "/opt/homebrew/bin/cloudflared" ]; then
    echo "/opt/homebrew/bin/cloudflared"
  elif [ -x "/usr/local/bin/cloudflared" ]; then
    echo "/usr/local/bin/cloudflared"
  else
    return 1
  fi
}

register_telegram_webhook() {
  local tunnel_url="$1"
  tunnel_url="${tunnel_url%/}"
  local webhook_url="${tunnel_url}/webhook/telegram"
  local bot_token="${TELEGRAM_BOT_TOKEN:-$(get_env_val TELEGRAM_BOT_TOKEN)}"
  local secret="${TELEGRAM_WEBHOOK_SECRET:-$(get_env_val TELEGRAM_WEBHOOK_SECRET)}"

  if [ -z "$bot_token" ]; then
    echo "Error: TELEGRAM_BOT_TOKEN is not set in environment or .env" >&2
    return 1
  fi

  local domain
  domain="$(echo "$tunnel_url" | sed -E 's#^https?://([^/:]+).*#\1#')"
  local resolved_ip=""
  if [[ "$domain" =~ \.trycloudflare\.com$ ]]; then
    resolved_ip="104.16.230.132"
  elif [ -n "$domain" ]; then
    resolved_ip="$(.venv/bin/python -c "import socket; print(socket.gethostbyname('$domain'))" 2>/dev/null || true)"
  fi

  echo "   Registering Telegram webhook -> $webhook_url (IP: ${resolved_ip:-DNS})..."
  local reg_res=""
  for attempt in 1 2 3 4 5 6; do
    if [ -z "$resolved_ip" ] && [ -n "$domain" ]; then
      resolved_ip="$(.venv/bin/python -c "import socket; print(socket.gethostbyname('$domain'))" 2>/dev/null || true)"
    fi

    local curl_cmd=(curl -s -X POST "https://api.telegram.org/bot${bot_token}/setWebhook" -d "url=${webhook_url}")
    if [ -n "$secret" ]; then
      curl_cmd+=(-d "secret_token=${secret}")
    fi
    if [ -n "$resolved_ip" ]; then
      curl_cmd+=(-d "ip_address=${resolved_ip}")
    fi

    reg_res="$("${curl_cmd[@]}")"
    if [[ "$reg_res" == *'"ok":true'* ]]; then
      echo "   ✅ Telegram Webhook registered successfully! (IP: ${resolved_ip:-DNS})"
      echo "   $reg_res"
      return 0
    fi
    sleep 2
  done

  echo "   ⚠️  Telegram Webhook registration result: $reg_res"
  return 1
}

PY_FORMAT_PATHS=(src tests evals)

cmd="${1:-help}"
shift || true

case "$cmd" in
  all|dev|start)
    TARGET_PORT="8000"
    if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then
      TARGET_PORT="$1"
      shift
    fi

    CLOUDFLARED_BIN="$(find_cloudflared || true)"

    echo "=================================================================="
    echo "🌍 Starting RoamAI (Omnichannel Companion) - All Services"
    echo "   Backend:  http://127.0.0.1:${TARGET_PORT}"
    echo "   Frontend: http://localhost:5173"
    if [ -n "$CLOUDFLARED_BIN" ]; then
      echo "   Tunnel:   Cloudflare Tunnel -> http://127.0.0.1:${TARGET_PORT}"
    else
      echo "   Tunnel:   ⚠️  cloudflared not found; skipping tunnel."
    fi
    echo "   Press Ctrl+C to stop all services."
    echo "=================================================================="

    PIDS=()
    cleanup() {
      trap - INT TERM EXIT
      echo ""
      echo "🛑 Shutting down all RoamAI services..."
      if [ "${#PIDS[@]}" -gt 0 ]; then
        for pid in "${PIDS[@]}"; do
          if kill -0 "$pid" 2>/dev/null; then
            kill -15 "$pid" 2>/dev/null || true
          fi
        done
        sleep 1
        for pid in "${PIDS[@]}"; do
          if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
          fi
        done
      fi
      exit 0
    }
    trap cleanup INT TERM EXIT

    # 1. Start Backend FastAPI
    .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port "$TARGET_PORT" --reload \
      --reload-dir src --reload-dir skills --no-access-log &
    BACKEND_PID=$!
    PIDS+=("$BACKEND_PID")

    # 2. Start Frontend Dev Server
    if [ -d "frontend" ] && command -v npm >/dev/null 2>&1; then
      (cd frontend && npm run dev) &
      FRONTEND_PID=$!
      PIDS+=("$FRONTEND_PID")
    fi

    # 3. Start Tunnel & Auto-register Telegram Webhook
    if [ -n "$CLOUDFLARED_BIN" ]; then
      TUNNEL_LOG="$(mktemp -t roam_tunnel.XXXXXX)"
      "$CLOUDFLARED_BIN" tunnel --url "http://127.0.0.1:${TARGET_PORT}" >"$TUNNEL_LOG" 2>&1 &
      TUNNEL_PID=$!
      PIDS+=("$TUNNEL_PID")

      (
        URL_FOUND=""
        for _ in $(seq 1 30); do
          if [ -s "$TUNNEL_LOG" ]; then
            URL_FOUND="$(grep -o 'https://[a-zA-Z0-9.-]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -n 1 || true)"
            if [ -n "$URL_FOUND" ]; then
              break
            fi
          fi
          sleep 1
        done

        if [ -n "$URL_FOUND" ]; then
          echo ""
          echo "✨ Cloudflare Tunnel established: $URL_FOUND"
          echo "   Webhook endpoint: ${URL_FOUND}/webhook/telegram"

          BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-$(get_env_val TELEGRAM_BOT_TOKEN)}"
          if [ -n "$BOT_TOKEN" ]; then
            register_telegram_webhook "$URL_FOUND" || true
          fi
          echo ""
        fi
      ) &
      WATCHER_PID=$!
      PIDS+=("$WATCHER_PID")
    fi

    wait "$BACKEND_PID"
    ;;
  app)
    TARGET_PORT="8000"
    if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then
      TARGET_PORT="$1"
      shift
    fi
    .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port "$TARGET_PORT" --reload \
      --reload-dir src --reload-dir skills --no-access-log
    ;;
  frontend)
    (cd frontend && npm run dev)
    ;;
  tunnel|tunnel:telegram|telegram:tunnel)
    CLOUDFLARED_BIN=""
    if command -v cloudflared >/dev/null 2>&1; then
      CLOUDFLARED_BIN="$(command -v cloudflared)"
    elif [ -x "/opt/homebrew/bin/cloudflared" ]; then
      CLOUDFLARED_BIN="/opt/homebrew/bin/cloudflared"
    elif [ -x "/usr/local/bin/cloudflared" ]; then
      CLOUDFLARED_BIN="/usr/local/bin/cloudflared"
    fi

    if [ -z "$CLOUDFLARED_BIN" ]; then
      echo "Error: 'cloudflared' command not found." >&2
      echo "Install Cloudflare Tunnel CLI via Homebrew: brew install cloudflared" >&2
      exit 1
    fi

    TARGET_PORT="8000"
    if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then
      TARGET_PORT="$1"
      shift
    fi

    echo "=================================================================="
    echo "🌍 Starting Cloudflare Tunnel for Telegram -> http://127.0.0.1:${TARGET_PORT}"
    echo "   Webhook endpoint: <TUNNEL_URL>/webhook/telegram"
    echo "   Once the tunnel URL is generated, register with Telegram via:"
    echo "     scripts/dev.sh telegram:webhook <TUNNEL_URL>"
    echo "=================================================================="
    exec "$CLOUDFLARED_BIN" tunnel --url "http://127.0.0.1:${TARGET_PORT}" "$@"
    ;;
  telegram:webhook|webhook:telegram)
    TUNNEL_URL="${1:-}"
    if [ -z "$TUNNEL_URL" ]; then
      echo "Usage: scripts/dev.sh telegram:webhook <TUNNEL_URL>" >&2
      echo "Example: scripts/dev.sh telegram:webhook https://xyz.trycloudflare.com" >&2
      exit 1
    fi
    register_telegram_webhook "$TUNNEL_URL"
    ;;
  telegram:info)
    BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-$(get_env_val TELEGRAM_BOT_TOKEN)}"
    if [ -z "$BOT_TOKEN" ]; then
      echo "Error: TELEGRAM_BOT_TOKEN is not set in environment or .env" >&2
      exit 1
    fi
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
    echo ""
    ;;
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
