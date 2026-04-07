# Используем официальный легковесный образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями в контейнер
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код проекта в рабочую директорию
COPY . .

# Создаём директорию для БД (для локального запуска / Docker Compose)
RUN mkdir -p /app/data

# На Railway persistent volume монтируется в /data,
# и DATABASE_PATH env var должен быть установлен в /data/users.db
CMD ["python", "bot.py"]