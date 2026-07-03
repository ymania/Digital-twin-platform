FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --proxy "" -i https://pypi.tuna.tsinghua.edu.cn/simple paho-mqtt

COPY edge_collector.py .

VOLUME /data

CMD ["python", "edge_collector.py"]
