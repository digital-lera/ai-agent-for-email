FROM python:3.11

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
RUN pip install --upgrade pip && pip install -r requirements.txt
RUN  python -m pip install paddlepaddle-gpu==3.3.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu130/


COPY . .

EXPOSE 8000
