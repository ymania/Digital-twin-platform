"""
Digital Twin - MQTT → InfluxDB Bridge

Subscribes to all room/* MQTT topics and writes each reading
as a time-series point to InfluxDB so Grafana can display it.
"""

import json
import os
import time

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

MQTT_HOST      = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT      = int(os.getenv("MQTT_PORT", 1883))
INFLUXDB_URL   = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "dt-super-secret-token-001")
INFLUXDB_ORG   = os.getenv("INFLUXDB_ORG", "digital-twin")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "room_sensors")

# Map MQTT topic suffix → InfluxDB field name + type
TOPIC_MAP = {
    "temperature": ("temperature_c",  float),
    "humidity":    ("humidity_pct",   float),
    "fan_speed":   ("fan_speed_rpm",  int),
    "fan_state":   ("fan_active",      lambda v: 1 if str(v).upper() == "ON" else 0),
    "light":       ("light_lux",      float),
    "power":       ("power_watts",    float),
}

influx_client = None
write_api = None


def init_influx():
    global influx_client, write_api
    print(f"[bridge] Connecting to InfluxDB at {INFLUXDB_URL} ...")
    while True:
        try:
            influx_client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG,
            )
            influx_client.ping()
            write_api = influx_client.write_api(write_options=SYNCHRONOUS)
            print("[bridge] InfluxDB connected.")
            break
        except Exception as e:
            print(f"[bridge] Waiting for InfluxDB... ({e})")
            time.sleep(3)


def on_connect(client, userdata, flags, rc):
    print(f"[bridge] Connected to MQTT broker (rc={rc})")
    client.subscribe("room/#")


def on_message(client, userdata, msg):
    topic_suffix = msg.topic.split("/")[-1]
    if topic_suffix not in TOPIC_MAP:
        return

    try:
        payload = json.loads(msg.payload.decode())
        raw = payload.get("value")
        field_name, cast = TOPIC_MAP[topic_suffix]
        value = cast(raw)
    except Exception as e:
        print(f"[bridge] Parse error on {msg.topic}: {e}")
        return

    point = (
        Point("room_environment")
        .tag("location", "room1")
        .field(field_name, value)
    )

    try:
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        print(f"[bridge] Written → {field_name}={value}")
    except Exception as e:
        print(f"[bridge] InfluxDB write error: {e}")


def main():
    init_influx()

    client = mqtt.Client(client_id="influx-bridge")
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[bridge] Connecting to MQTT {MQTT_HOST}:{MQTT_PORT} ...")
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except Exception as e:
            print(f"[bridge] Waiting for MQTT broker... ({e})")
            time.sleep(3)

    client.loop_forever()


if __name__ == "__main__":
    main()
