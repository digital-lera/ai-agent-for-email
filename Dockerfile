FROM ollama/ollama:latest

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 11434
EXPOSE 5000

# Запускаем Ollama в фоне, затем Gunicorn
CMD ["sh", "-c", "ollama serve & sleep 5 && gunicorn --bind 0.0.0.0:5000 --workers 1 app:app"]