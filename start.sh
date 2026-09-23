#!/bin/bash
echo "=== Быстрый старт сервера (Всё в Docker) ==="

echo "[1/2] Сборка и запуск контейнеров (Веб-сервер + Ollama)..."
# Запускаем docker-compose. Флаг -d означает запуск в фоне.
docker-compose up --build -d

echo "[2/2] Скачивание модели qwen2.5:7b (Быстрая версия для тестов)..."
echo "Это не займет много времени."
docker exec spark-dossier-ollama ollama pull qwen2.5:7b

echo ""
echo "=== ВСЁ УСПЕШНО ЗАПУЩЕНО! ==="
echo "Ваш сервер доступен по адресу: http://<ip-вашего-сервера> (через Nginx)"


