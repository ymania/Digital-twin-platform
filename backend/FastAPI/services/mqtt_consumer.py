"""
Digital Twin Backend — MQTT Consumer Service

职责：
  1. 订阅 EMQX telemetry/alarm
  2. 写 InfluxDB（时序存储）
  3. 更新内存状态机矩阵 + WebSocket 增量推送

Phase 2 红线：不直写 PG，asset_id→bim_guid 映射走 PG 缓存。
"""
import os
import json
import asyncio
import logging

import paho.mqtt.client as mqtt
from influxdb_client.client.write_api import SYNCHRONOUS

from database.influx import get_client
from core.state import GLOBAL_TWIN_MATRIX, TwinState, derive_status
from routers.ws import manager

logger = logging.getLogger("dt.mqtt")

MQTT_TOPICS = [
    ("industrial_twin/+/telemetry/data", 0),
    ("industrial_twin/+/event/alarm", 2),
]
client: mqtt.Client | None = None
_loop: asyncio.AbstractEventLoop | None = None


def on_connect(c, userdata, flags, rc, properties=None):
    rc_val = rc.value if hasattr(rc, "value") else rc
    logger.info("MQTT connected (rc=%s), subscribing...", rc_val)
    for topic, qos in MQTT_TOPICS:
        c.subscribe(topic, qos=qos)


def on_message(c, userdata, msg):
    if not _loop:
        return
    asyncio.run_coroutine_threadsafe(handle_message(msg.topic, msg.payload), _loop)


async def handle_message(topic: str, raw_payload: bytes):
    try:
        data = json.loads(raw_payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    if "telemetry" in topic:
        await handle_telemetry(data)
    # alarm handling — Phase 4


async def handle_telemetry(data: dict):
    """边缘遥测 → InfluxDB + 状态机 + WS 推送"""
    metrics = data.get("metrics", {})
    units = data.get("unit", {})
    statuses = data.get("status", {}) or {}
    timestamp = data.get("timestamp")
    edge_id = data.get("asset_id", "unknown")

    for status_key, current_status in statuses.items():
        parts = status_key.split("/", 1)
        if len(parts) != 2:
            continue
        metric_name, asset_id = parts
        value = metrics.get(metric_name)
        if value is None:
            continue

        value_f = float(value)

        # 1. InfluxDB 写入（纳秒精度）
        _write_influx(metric_name, asset_id, edge_id, value_f, units.get(metric_name, ""), timestamp)

        # 2. 查 PG → bim_guid
        bim_guid = await _resolve_bim_guid(asset_id)
        if not bim_guid:
            bim_guid = f"BIM_{asset_id}"

        # 3. 状态机 + WS 广播
        new_state = TwinState(
            guid=bim_guid,
            status=derive_status(metric_name, value_f),
            value=value_f,
            timestamp=timestamp or 0,
            metric=metric_name,
        )
        old = GLOBAL_TWIN_MATRIX.get(bim_guid)
        if old is None or old.status != new_state.status or abs(old.value - new_state.value) > 0.5:
            GLOBAL_TWIN_MATRIX[bim_guid] = new_state
            asyncio.ensure_future(manager.broadcast({
                "guid": bim_guid,
                "status": new_state.status,
                "value": value_f,
                "metric": metric_name,
                "asset_id": asset_id,
                "timestamp": timestamp,
            }))


def _write_influx(metric: str, asset_id: str, edge_id: str, value: float, unit: str, timestamp):
    """InfluxDB 写入。不传 time 用服务器时钟，传则纳秒精度"""
    try:
        bucket = os.getenv("INFLUXDB_BUCKET", "telemetry")
        org = os.getenv("INFLUXDB_ORG", "dt_platform")
        point = {
            "measurement": metric,
            "tags": {"asset_id": asset_id, "edge_id": edge_id},
            "fields": {"value": value, "unit_str": unit},
        }
        if timestamp:
            point["time"] = timestamp * 1_000_000  # ms → ns
        write_api = get_client().write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=bucket, org=org, record=point)
    except Exception:
        logger.warning("InfluxDB write failed (non-fatal)", exc_info=True)


async def _resolve_bim_guid(asset_name: str) -> str | None:
    """PostgreSQL 查 bim_guid"""
    try:
        from database import get_pool
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT bim_guid FROM asset WHERE asset_name = $1", asset_name
        )
        return row["bim_guid"] if row else None
    except Exception:
        return None


async def start_mqtt():
    global client, _loop
    _loop = asyncio.get_running_loop()
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))

    client = mqtt.Client(client_id="dt-backend-consumer", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect_async(host, port, keepalive=60)
        client.loop_start()
        logger.info("MQTT consumer started: %s:%s", host, port)
    except Exception as e:
        logger.warning("MQTT connect failed (non-fatal): %s", e)
    return client


async def stop_mqtt():
    global client
    if client:
        client.loop_stop()
        client.disconnect()
        client = None
