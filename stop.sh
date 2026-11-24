#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER="docker compose"

if [ "$1" = "prod" ]; then
  echo "Останавливаю production stack..."
  $DOCKER -f "$SCRIPT_DIR/docker-compose.yml" --profile prod down
  echo "Готово"
  exit 0
fi

echo "=== Остановка dev-окружения ==="

echo "Останавливаю бэкенд (порт 8000)..."
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "Готово" || echo "Уже остановлен"

echo "Останавливаю фронтенд (порт 3000)..."
lsof -ti:3000 | xargs kill -9 2>/dev/null && echo "Готово" || echo "Уже остановлен"

echo "Останавливаю инфраструктуру..."
$DOCKER -f "$SCRIPT_DIR/docker-compose.yml" stop postgres opensearch qdrant
echo "Готово"

echo ""
echo "Всё остановлено."
