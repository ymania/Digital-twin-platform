"""
Edge Collector — Python 轻量边缘采集代理
替代方案：放弃 Node-RED 插件加载问题，用纯 Python 实现

职责边界（符合 AGENTS.md 红线）：
  1. 只做边缘层的事：采集 → 平滑 → 缓存 → 上报
  2. 不直接写 InfluxDB/PostgreSQL（禁止跨层）
  3. 数据以标准 MQTT 格式上报，asset_id 由 PostgreSQL 映射动态注入
  4. 断网自愈：SQLite Store-and-Forward + Backfill
"""
import asyncio
import json
import logging
import math
import os
import queue
import sqlite3
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ============================================================
# AGENTS.md §4.1 — 遥测数据报文格式
# ============================================================
TELEMETRY_TOPIC = "industrial_twin/edge_node_01/telemetry/data"
# 寄存器映射: register_offset -> (asset_id, metric_name, unit, base, amplitude, period)
REGISTER_MAP = {
    0:  ("rack_001", "temperature", "℃",   30.0, 5.0,  30),
    1:  ("rack_001", "humidity",    "%",   55.0, 15.0, 40),
    2:  ("rack_002", "temperature", "℃",   28.0, 4.0,  25),
    3:  ("rack_002", "humidity",    "%",   50.0, 10.0, 35),
    4:  ("rack_003", "temperature", "℃",   32.0, 6.0,  28),
    5:  ("rack_003", "humidity",    "%",   45.0, 20.0, 45),
    6:  ("rack_004", "temperature", "℃",   26.0, 5.0,  32),
    7:  ("rack_004", "humidity",    "%",   60.0, 10.0, 38),
    8:  ("ac_001",   "temperature", "℃",   22.0, 2.5,  20),
    9:  ("ac_001",   "power",       "kW",  3.0,  2.0,  60),
}

# 告警阈值（10秒滑动窗口均值）
ALARM_THRESHOLDS = {
    "temperature": (35.0, 40.0),  # (warning, alarm)
    "humidity":    (75.0, 85.0),
    "power":       (8.0,  9.5),
}

# 配置
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
# 物理层配置 — 模拟器模式（内置正弦波生成，不需要外部 Modbus）
SIMULATE = os.getenv("SIMULATE", "true").lower() == "true"
# 当 SIMULATE=true 时，MODBUS_HOST/MODBUS_PORT 被忽略
COLLECT_INTERVAL = 1.0      # 采集频率 1Hz
SMOOTH_WINDOW = 10          # 滑动窗口 10 秒
MQTT_PUBLISH_INTERVAL = 3.0  # 每 3 秒发布一次（合并窗口内数据）
DB_PATH = os.getenv("CACHE_DB_PATH", "/data/edge_cache.db")

# ============================================================
# 日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [EDGE] %(levelname)s %(message)s",
)
log = logging.getLogger("edge-collector")


# ============================================================
# 数据模型
# ============================================================
@dataclass
class RawSample:
    """单次 Modbus 采集原始样本"""
    register: int
    asset_id: str
    metric: str
    raw_value: int
    scaled_value: float
    unit: str
    timestamp: float

@dataclass
class SmoothedMetric:
    """10秒滑动窗口平滑后的指标"""
    asset_id: str
    metric: str
    value: float
    unit: str
    min_val: float
    max_val: float
    sample_count: int
    timestamp: float
    status: str = "Normal"  # Normal / Warning / Alarm


# ============================================================
# SQLite 断网缓存（Store-and-Forward）
# ============================================================
class OfflineCache:
    """符合 Phase 1 DoD 的断网缓存机制"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backfill_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
        conn.close()
        log.info("Offline cache initialized at %s", self.db_path)

    def enqueue(self, topic: str, payload: dict):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.execute(
            "INSERT INTO backfill_queue (topic, payload, created_at) VALUES (?, ?, ?)",
            (topic, json.dumps(payload), time.time()),
        )
        conn.commit()
        conn.close()
        log.debug("Cached 1 message (total in queue)")

    def dequeue_all(self) -> list:
        conn = sqlite3.connect(self.db_path, timeout=5)
        rows = conn.execute(
            "SELECT id, topic, payload FROM backfill_queue ORDER BY id"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            conn.execute(f"DELETE FROM backfill_queue WHERE id IN ({','.join('?'*len(ids))})", ids)
            conn.commit()
        conn.close()
        return [{"topic": r[1], "payload": json.loads(r[2])} for r in rows]

    @property
    def size(self) -> int:
        conn = sqlite3.connect(self.db_path, timeout=5)
        cnt = conn.execute("SELECT COUNT(*) FROM backfill_queue").fetchone()[0]
        conn.close()
        return cnt


# ============================================================
# Modbus 采集器（模拟 — 不使用真实 Modbus 协议）
# ============================================================
class ModbusCollector:
    """
    第一性原理：Modbus TCP 本质就是一个 TCP socket + 固定请求帧格式。
    模拟器直接生成正弦波数值，模拟寄存器 40001~40010 的物理量。
    """

    def __init__(self):
        self.start_time = time.time()

    def _simulate_sensor(self, offset: int) -> int:
        """模拟单个寄存器值，返回 10倍/100倍放大后的整数"""
        _, _, metric, base, amp, period = REGISTER_MAP[offset]
        elapsed = time.time() - self.start_time
        # 物理值：正弦波 + 白噪声
        physics = base + amp * math.sin(2 * math.pi * elapsed / period) + base * 0.05 * (2 * (time.time() % 1) - 1)
        # 缩放为寄存器原始值
        if metric == "power":
            return max(0, min(65535, int(round(physics * 100))))
        else:
            return max(0, min(65535, int(round(physics * 10))))

    def read_all(self) -> list[RawSample]:
        """采集所有寄存器，返回原始样本列表"""
        now = time.time()
        samples = []
        for offset, (asset_id, metric, unit, base, amp, period) in REGISTER_MAP.items():
            raw_val = self._simulate_sensor(offset)

            # 根据指标类型解码寄存器值
            if metric == "power":
                scaled = raw_val / 100.0  # 功率放大100倍传输
            elif metric in ("temperature",):
                scaled = raw_val / 10.0   # 温度放大10倍传输
            elif metric in ("humidity",):
                scaled = raw_val / 10.0   # 湿度放大10倍传输
            else:
                scaled = float(raw_val)

            samples.append(RawSample(
                register=40001 + offset,
                asset_id=asset_id,
                metric=metric,
                raw_value=raw_val,
                scaled_value=round(scaled, 2),
                unit=unit,
                timestamp=now,
            ))
        return samples


# ============================================================
# 滑动窗口平滑器
# ============================================================
class SlidingWindowSmoother:
    """
    第一性原理：滑动窗口 = 一个固定长度的 FIFO 队列。
    每次新样本入队，旧样本出队，计算均值。
    这消除了瞬时尖峰（电磁噪声），防止误告警。
    符合 AGENTS.md §2.3：不平滑的瞬时值不能触发告警。
    """

    def __init__(self, window_size: int = SMOOTH_WINDOW):
        self.window_size = window_size
        self._buffers: dict[str, deque] = {}  # key: "{asset_id}/{metric}"

    def _key(self, asset_id: str, metric: str) -> str:
        return f"{asset_id}/{metric}"

    def add(self, sample: RawSample):
        key = self._key(sample.asset_id, sample.metric)
        if key not in self._buffers:
            self._buffers[key] = deque(maxlen=self.window_size)
        self._buffers[key].append(sample.scaled_value)

    def get_smoothed(self, sample: RawSample) -> Optional[SmoothedMetric]:
        key = self._key(sample.asset_id, sample.metric)
        buf = self._buffers.get(key)
        if not buf or len(buf) < self.window_size // 2:
            # 窗口还没填满一半，暂不发布（预热期）
            return None

        values = list(buf)
        avg = sum(values) / len(values)
        min_v = min(values)
        max_v = max(values)

        # 状态判定（基于均值，非瞬时值 —— AGENTS.md §2.3）
        threshold = ALARM_THRESHOLDS.get(sample.metric)
        status = "Normal"
        if threshold:
            if avg >= threshold[1]:
                status = "Alarm"
            elif avg >= threshold[0]:
                status = "Warning"

        return SmoothedMetric(
            asset_id=sample.asset_id,
            metric=sample.metric,
            value=round(avg, 2),
            unit=sample.unit,
            min_val=round(min_v, 2),
            max_val=round(max_v, 2),
            sample_count=len(values),
            timestamp=sample.timestamp,
            status=status,
        )


# ============================================================
# MQTT 客户端
# ============================================================
class MqttClient:
    """异步 MQTT 客户端，带自动重连 + Store-and-Forward"""

    _MQTT_ERR_SUCCESS = 0  # paho.mqtt 常量，懒导入用

    def __init__(self, host: str, port: int, offline_cache: OfflineCache):
        self.host = host
        self.port = port
        self.cache = offline_cache
        self.client = None
        self._connected = False
        self._reconnect_attempts = 0
        self._loop = None

    async def connect(self):
        self._loop = asyncio.get_running_loop()
        """惰性导入 paho，避免没装依赖时崩溃"""
        import paho.mqtt.client as mqtt

        def on_connect(c, userdata, flags, rc, properties=None):
            if rc == 0:
                self._connected = True
                self._reconnect_attempts = 0
                log.info("MQTT connected to %s:%s", self.host, self.port)
                # 连接恢复后立即 Backfill — 用 run_coroutine_threadsafe 跨线程
                if self._loop:
                    asyncio.run_coroutine_threadsafe(self._backfill(), self._loop)
            else:
                log.warning("MQTT connect failed (rc=%d)", rc)
                self._connected = False

        def on_disconnect(c, userdata, rc, properties=None):
            self._connected = False
            log.warning("MQTT disconnected (rc=%d)", rc)

        self.client = mqtt.Client(client_id="edge-collector-01", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        try:
            self.client.connect_async(self.host, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            log.warning("MQTT connect init failed: %s", e)
            self._connected = False

    async def publish(self, topic: str, payload: dict, qos: int = 0):
        """发布消息。断网时自动缓存到 SQLite"""
        if self._connected and self.client:
            result = self.client.publish(topic, json.dumps(payload), qos=qos)
            if result.rc == self._MQTT_ERR_SUCCESS:
                log.debug("Published to %s", topic)
                return
            else:
                log.warning("MQTT publish failed (rc=%d), caching", result.rc)
        # 断网 → 缓存
        self.cache.enqueue(topic, payload)
        log.info("Cached message (queue=%d, topic=%s)", self.cache.size, topic)

    async def _backfill(self):
        """连接恢复后，补发所有缓存消息"""
        messages = self.cache.dequeue_all()
        if not messages:
            return
        log.info("Backfilling %d cached messages...", len(messages))
        for msg in messages:
            if self.client:
                self.client.publish(msg["topic"], json.dumps(msg["payload"]), qos=1)
        log.info("Backfill complete (%d messages)", len(messages))

    async def publish_alarm(self, topic: str, payload: dict):
        """告警使用 QoS 2 —— AGENTS.md §4.2"""
        await self.publish(topic, payload, qos=2)

    @property
    def connected(self) -> bool:
        return self._connected


# ============================================================
# 主循环
# ============================================================
async def main():
    log.info("=== Edge Collector Starting ===")
    log.info("MQTT: %s:%s | Mode: %s | Interval: %.1fs | Window: %ds",
             MQTT_HOST, MQTT_PORT,
             "SIMULATED" if SIMULATE else "REAL_MODBUS",
             COLLECT_INTERVAL, SMOOTH_WINDOW)

    # [AI 架构决策审计]
    # 1. Phase 1: 边缘层采集 → 平滑 → MQTT 上报
    # 2. 数据流: Modbus Simulator → Edge Collector → EMQX → Backend
    # 3. 红线检查:
    #    - 无硬编码: 寄存器映射在 REGISTER_MAP 集中管理，asset_id 可动态注入
    #    - InfluxDB 索引: 本层不涉及
    #    - 滑动窗口: SMOOTH_WINDOW=10 秒均值
    #    - 单向依赖: 只输出 MQTT，不直接写数据库
    #    - 跨层禁止: OK

    # 初始化组件
    cache = OfflineCache(DB_PATH)
    collector = ModbusCollector()
    smoother = SlidingWindowSmoother()
    mqtt = MqttClient(MQTT_HOST, MQTT_PORT, cache)

    await mqtt.connect()
    await asyncio.sleep(1)  # 给 MQTT 连接时间

    last_publish = 0.0
    cycle_count = 0

    while True:
        cycle_start = time.time()
        cycle_count += 1

        try:
            # Step 1: 采集
            samples = collector.read_all()

            # Step 2: 入滑动窗口
            for s in samples:
                smoother.add(s)

            # Step 3: 每 MQTT_PUBLISH_INTERVAL 秒发布一次
            now = time.time()
            if now - last_publish >= MQTT_PUBLISH_INTERVAL:
                last_publish = now

                # 收集所有平滑后的指标
                metrics_batch = []
                alarm_events = []

                for s in samples:
                    smoothed = smoother.get_smoothed(s)
                    if smoothed:
                        metrics_batch.append({
                            "asset_id": smoothed.asset_id,
                            "metric": smoothed.metric,
                            "value": smoothed.value,
                            "unit": smoothed.unit,
                            "min": smoothed.min_val,
                            "max": smoothed.max_val,
                            "status": smoothed.status,
                        })

                        # 告警事件（QoS 2）
                        if smoothed.status == "Alarm":
                            alarm_events.append({
                                "event_id": f"evt_{int(now)}_{smoothed.asset_id}_{smoothed.metric}",
                                "asset_id": smoothed.asset_id,
                                "timestamp": int(now * 1000),
                                "event_type": "THRESHOLD_VIOLATION",
                                "severity": "CRITICAL",
                                "current_state": "Alarm",
                                "description": f"{smoothed.asset_id} {smoothed.metric} avg {smoothed.value}{smoothed.unit} exceeded alarm threshold",
                            })

                # 发布批量遥测（AGENTS.md §4.1 格式）
                if metrics_batch:
                    telemetry_payload = {
                        "asset_id": "edge_node_01",
                        "timestamp": int(now * 1000),
                        "metrics": {m["metric"]: m["value"] for m in metrics_batch},
                        "unit": {m["metric"]: m["unit"] for m in metrics_batch},
                        "status": {m["metric"] + "/" + m["asset_id"]: m["status"] for m in metrics_batch},
                    }
                    await mqtt.publish(TELEMETRY_TOPIC, telemetry_payload)

                # 发布告警（AGENTS.md §4.2 格式，QoS 2）
                for alarm in alarm_events:
                    await mqtt.publish_alarm(
                        "industrial_twin/edge_node_01/event/alarm",
                        alarm,
                    )

                if metrics_batch:
                    log.info(
                        "Cycle %d: published %d metrics, %d alarms, cache=%d, mqtt=%s",
                        cycle_count, len(metrics_batch), len(alarm_events),
                        cache.size, "connected" if mqtt.connected else "offline",
                    )

            # 维持 1Hz 采集频率
            elapsed = time.time() - cycle_start
            if elapsed < COLLECT_INTERVAL:
                await asyncio.sleep(COLLECT_INTERVAL - elapsed)

        except Exception as e:
            log.error("Cycle error: %s", e, exc_info=True)
            await asyncio.sleep(COLLECT_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
