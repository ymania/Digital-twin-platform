# Digital Twin Backend — Dockerfile
FROM python:3.12-slim

# Kill inherited proxy from host
ENV http_proxy=
ENV https_proxy=
ENV HTTP_PROXY=
ENV HTTPS_PROXY=

WORKDIR /app

# Install system deps (use mirrors)
RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# App code
COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
