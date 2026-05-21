FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator.py .

RUN adduser --system --no-create-home appuser
USER appuser

CMD ["python", "simulator.py"]
