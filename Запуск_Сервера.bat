@echo off
chcp 65001 >nul
title Запуск сервера Offline Dossier

echo ========================================================
echo         ЗАПУСК СИСТЕМЫ OFFLINE DOSSIER (DOCKER)
echo ========================================================
echo.

echo [1/3] Подготовка и запуск контейнеров (Веб-сервер + Ollama)...
docker-compose up --build -d
echo.

echo [2/3] Инициализация нейросети...
echo Скачивание модели orcarouter/Qwen3.8-27B-Uncensored.
echo Пожалуйста, подождите. Это может занять время...
docker exec spark-dossier-ollama ollama pull orcarouter/Qwen3.8-27B-Uncensored
echo.

echo [3/3] Запуск интерфейса...
echo Сервер успешно запущен! Открываю браузер...
timeout /t 3 >nul
start http://localhost:8080

echo.
echo ========================================================
echo Готово! Вы можете свернуть это окно (но не закрывайте его,
echo если хотите видеть логи, хотя система работает в фоне).
echo ========================================================
pause
