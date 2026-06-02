FROM python:3.11-slim

WORKDIR /app

# Установить необходимые зависимости для Ollama и системы
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установить Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt && pip install gunicorn

COPY . .

EXPOSE 11434
EXPOSE 5000

# Запускаем Ollama в фоне, затем Gunicorn
CMD ["sh", "-c", "ollama serve & sleep 5 && gunicorn --bind 0.0.0.0:5000 --workers 1 app:app"]