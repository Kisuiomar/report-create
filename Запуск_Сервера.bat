@echo off
title Offline Dossier Server Launcher

echo ========================================================
echo         STARTING OFFLINE DOSSIER SYSTEM (DOCKER)
echo ========================================================
echo.

echo [1/3] Building and starting containers (Web Server + Ollama)...
docker-compose up --build -d
echo.

echo [2/3] Initializing Neural Network...
echo Downloading model orcarouter/Qwen3.8-27B-Uncensored.
echo Please wait, this might take a significant amount of time...
docker exec spark-dossier-ollama ollama pull orcarouter/Qwen3.8-27B-Uncensored
echo.

echo [3/3] Launching Web Interface...
echo Server successfully started! Opening browser...
timeout /t 3 >nul
start http://localhost:8080

echo.
echo ========================================================
echo DONE! You may minimize this window.
echo ========================================================
pause
