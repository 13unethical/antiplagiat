#!/bin/bash
# Usage:
#   ./start.sh       — dev mode: Docker infra + local backend/frontend
#   ./start.sh prod  — prod mode: full Docker stack

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER="docker compose"

if [ "$1" = "prod" ]; then
  echo "=== Production start (full Docker stack) ==="
  $DOCKER -f "$SCRIPT_DIR/docker-compose.yml" --profile prod up --build -d
  echo ""
  echo "  Frontend: http://localhost:3000"
  echo "  API docs: http://localhost:8000/docs"
  echo ""
  echo "Logs: docker compose --profile prod logs -f"
  exit 0
fi

echo "=== Dev start: инфраструктура + локальный backend/frontend ==="

echo "[1/3] Запуск инфраструктуры (postgres, opensearch, qdrant)..."
$DOCKER -f "$SCRIPT_DIR/docker-compose.yml" up -d postgres opensearch qdrant
echo "      Готово"

echo "[2/3] Запуск бэкенда (порт 8000)..."
cd "$SCRIPT_DIR/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "      PID: $BACKEND_PID"

echo "[3/3] Запуск фронтенда (порт 3000)..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
echo "      PID: $FRONTEND_PID"

echo ""
echo "================================"
echo "  Фронтенд:  http://localhost:3000"
echo "  API docs:  http://localhost:8000/docs"
echo "================================"
echo "Для остановки нажмите Ctrl+C"
echo ""

trap "echo ''; echo 'Останавливаю...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
