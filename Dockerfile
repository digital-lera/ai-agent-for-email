FROM python:3.11-slim
WORKDIR ./

COPY requirements.txt ./
RUN pip3 install --upgrade pip -r requirements.txt

COPY . .

EXPOSE 5000



