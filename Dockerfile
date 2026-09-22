FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей, необходимых для сборки некоторых python-пакетов и работы OCR
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Запуск веб-сервера
CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8080"]
