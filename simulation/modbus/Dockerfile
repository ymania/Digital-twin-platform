# Modbus Simulator
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir pymodbus>=3.8

COPY simulator.py .

EXPOSE 5020

CMD ["python", "simulator.py"]
