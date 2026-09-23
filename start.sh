#!/bin/bash
echo "=== Быстрый старт сервера (Всё в Docker) ==="

echo "[1/2] Сборка и запуск контейнеров (Веб-сервер + Ollama)..."
# Запускаем docker-compose. Флаг -d означает запуск в фоне.
docker-compose up --build -d

echo "[2/2] Скачивание моделей (Qwen 27B и Nomic-Embed-Text)..."
echo "Это может занять значительное время в зависимости от скорости интернета."
docker exec spark-dossier-ollama ollama pull orcarouter/Qwen3.8-27B-Uncensored
docker exec spark-dossier-ollama ollama pull nomic-embed-text

echo ""
echo "=== ВСЁ УСПЕШНО ЗАПУЩЕНО! ==="
echo "Ваш сервер доступен по адресу: http://<ip-вашего-сервера> (через Nginx)"


