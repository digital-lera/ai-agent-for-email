FROM python:3.9-slim

ENV FLAGS_allocator_strategy=naive_best_fit
ENV SET_FLAGS_USING_AVX=0

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    zstd \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    poppler-utils \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip 
RUN cat requirements.txt | xargs -n 1 pip install



COPY . .

EXPOSE 8000
