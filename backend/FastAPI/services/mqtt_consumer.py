"""
Digital Twin Backend — MQTT Consumer Service

Subscribes to EMQX, writes telemetry to InfluxDB,
and broadcasts via WebSocket.

使用 paho-mqtt（与 edge collector 一致），替代 gmqtt。
"""
import os
import json
import asyncio
import logging
import threading

import paho.mqtt.client as mqtt

from database.influx import write_api

logger = logging.getLogger("dt.mqtt")

MQTT_TOPICS = [
    ("industrial_twin/+/telemetry/data", 0),
    ("industrial_twin/+/event/alarm", 2),
    ("industrial_twin/+/status/#", 1),
]

client: mqtt.Client | None = None
_loop: asyncio.AbstractEventLoop | None = None


def on_connect(c, userdata, flags, rc, properties=None):
    rc_val = rc.value if hasattr(rc, 'value') else rc
    logger.info("MQTT connected (rc=%s)", rc_val)
    for topic, qos in MQTT_TOPICS:
        c.subscribe(topic, qos=qos)
        logger.info("Subscribed to %s (qos=%d)", topic, qos)


def on_message(c, userdata, msg):
    """paho-mqtt 回调在后台线程中运行"""
    logger.info("RAW MQTT MSG: topic=%s, len=%d", msg.topic, len(msg.payload))
    if not _loop:
        return
    asyncio.run_coroutine_threadsafe(handle_message(msg.topic, msg.payload), _loop)


async def handle_message(topic: str, raw_payload: bytes):
    try:
        data = json.loads(raw_payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Invalid MQTT payload on %s: %s", topic, e)
        return

    if "telemetry" in topic:
        await handle_telemetry(topic, data)
    elif "alarm" in topic:
        await handle_alarm(topic, data)


async def handle_telemetry(topic: str, data: dict):
    """Write telemetry to InfluxDB and broadcast"""
    logger.info("HANDLE_TELEMETRY: metrics=%s", list(data.get('metrics', {}).keys()))
    bucket = os.getenv("INFLUXDB_BUCKET", "telemetry")
    org = os.getenv("INFLUXDB_ORG", "dt_platform")

    metrics = data.get("metrics", {})
    units = data.get("unit", {})
    statuses = data.get("status", {}) or {}
    timestamp = data.get("timestamp")
    edge_id = data.get("asset_id", "unknown")

    for metric_name, value in metrics.items():
        if value is None:
            continue

        # 从 status 字典反推 asset_id (key = "metric/asset_id")
        asset_id = edge_id
        for key, st in statuses.items():
            if key.startswith(metric_name + "/"):
                asset_id = key.split("/", 1)[1]
                break

        logger.info("InfluxDB WRITE: bucket=%s measurement=%s asset_id=%s value=%.2f",
                     bucket, metric_name, asset_id, float(value))

        point = {
            "measurement": metric_name,
            "tags": {
                "asset_id": str(asset_id),
                "edge_id": str(edge_id),
            },
            "fields": {
                "value": float(value),
                "unit_str": units.get(metric_name, ""),
            },
        }
        if timestamp:
            point["time"] = timestamp

        try:
            result = write_api().write(bucket=bucket, org=org, record=point)
            logger.info("InfluxDB WRITE OK: %s/%s=%.2f (result=%s)",
                        metric_name, asset_id, float(value), result)
        except Exception as e:
            logger.error("InfluxDB WRITE FAILED: %s/%s=%.2f — %s",
                         metric_name, asset_id, float(value), str(e))

        # ============================================================
        # 状态机跳变 + WebSocket 增量推送（晚收官战契约）
        # ============================================================
        from core.state import GLOBAL_TWIN_MATRIX, TwinState, derive_status

        # 通过 metric+asset_id 组合生成伪 GUID（Phase 2 真正上线时由 PG 映射）
        bim_guid = f"BIM_{asset_id}_{metric_name}"

        current_status = statuses.get(f"{metric_name}/{asset_id}", "Normal")
        # 如果边缘层没传递状态，用 backend 自己的阈值判定
        if current_status == "Normal":
            current_status = derive_status(metric_name, float(value))

        new_state = TwinState(
            guid=bim_guid,
            status=current_status,
            value=float(value),
            timestamp=timestamp or 0,
            metric=metric_name,
        )

        # 状态机收敛：只有发生跳变时才广播
        old_state = GLOBAL_TWIN_MATRIX.get(bim_guid)
        if old_state is None or old_state.status != new_state.status or abs(old_state.value - new_state.value) > 0.5:
            GLOBAL_TWIN_MATRIX[bim_guid] = new_state
            # 通过 run_coroutine_threadsafe 安全跨线程推送
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                from routers.ws import broadcast_twin_state
                broadcast_twin_state({
                    "guid": bim_guid,
                    "status": current_status,
                    "value": float(value),
                    "metric": metric_name,
                    "asset_id": asset_id,
                    "timestamp": timestamp,
                })
                logger.info("STATE JUMP: %s → %s (%.1f)", bim_guid, current_status, float(value))

        # (旧 broadcast_telemetry 已被状态机广播取代)


async def check_alarms(asset_id: int, sensor_id: int, measurement: str, value: float):
    """Evaluate alarm rules for a sensor"""
    pool = await get_pool()
    rules = await pool.fetch(
        "SELECT * FROM alarm_rule WHERE sensor_id = $1 AND enabled = TRUE",
        sensor_id
    )
    for rule in rules:
        triggered = False
        cond = rule["condition"]
        if cond == "gt" and value > rule["threshold"]:
            triggered = True
        elif cond == "lt" and value < rule["threshold"]:
            triggered = True
        elif cond == "range" and rule["threshold_high"]:
            if value < rule["threshold"] or value > rule["threshold_high"]:
                triggered = True
        elif cond == "eq" and abs(value - rule["threshold"]) < 0.001:
            triggered = True

        if triggered:
            await pool.execute(
                """INSERT INTO alarm_event (rule_id, asset_id, sensor_id, value, severity, message)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                rule["rule_id"], asset_id, sensor_id, value,
                rule["severity"],
                f"{rule['alarm_name']}: {value:.1f} (threshold: {rule['threshold']})"
            )
            await broadcast_alarm({
                "type": "alarm",
                "asset_id": asset_id,
                "sensor_id": sensor_id,
                "severity": rule["severity"],
                "message": rule["alarm_name"],
                "value": value,
                "timestamp": "",
            })


async def handle_alarm(topic: str, data: dict):
    """Forward edge-originated alarms — TODO: integrate with state machine"""
    pass


async def start_mqtt():
    """Start paho-mqtt client for consuming edge telemetry"""
    global client, _loop
    _loop = asyncio.get_running_loop()
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))

    client = mqtt.Client(
        client_id="dt-backend-consumer",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect_async(host, port, keepalive=60)
        client.loop_start()
        logger.info("MQTT client connected to %s:%s", host, port)
    except Exception as e:
        logger.warning("MQTT connection failed: %s", e)

    return client


async def stop_mqtt():
    global client
    if client:
        client.loop_stop()
        client.disconnect()
        client = None
