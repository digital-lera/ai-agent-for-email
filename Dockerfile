FROM ollama/ollama:latest
FROM python:3.11-slim

# Copy your project
COPY . .
WORKDIR /



COPY requirements.txt ./
RUN pip3 install --upgrade pip -r requirements.txt

# Expose Ollama port
EXPOSE 11434

EXPOSE 5000

# Start Ollama and keep the model loaded
CMD ["ollama", "run", "bambucha/saiga-llama3"]
