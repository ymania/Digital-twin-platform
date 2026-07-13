# Digital Twin Platform — 工业数字孪生平台

## 架构概览

**两套独立栈，共享网络，各司其职。**

```
┌──────────────────────────────────────────────────────────────┐
│ Docker network: digital-twin_default                         │
│                                                              │
│  ┌─ 底座 (room-digital-twin) ───────────────────────────┐   │
│  │  sensor_simulator → mosquitto (MQTT) → mqtt_bridge    │   │
│  │                            ↓              ↓           │   │
│  │                         viz3d         influxdb         │   │
│  │                                         ↓              │   │
│  │                                      grafana           │   │
│  └────────────────────────────────────────────────────────┘   │
│                           │ MQTT  1883                        │
│                           ▼                                   │
│  ┌─ 扩展层 (BIM + Twin Service) ─────────────────────────┐   │
│  │  FastAPI (Twin Service) ← 订阅 MQTT 数据               │   │
│  │     ├── PostgreSQL（资产/传感器/告警规则）               │   │
│  │     └── WebSocket → Three.js (BIM 3D 渲染)             │   │
│  └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 底座层

| 组件 | 技术栈 | 端口 | 职责 |
|------|--------|------|------|
| sensor_simulator | Python + paho-mqtt | — | 物理模型仿真（温度/湿度/风扇/光照/功率） |
| mosquitto | eclipse-mosquitto:2 | 1883, 9001 | MQTT Broker（TCP + WebSocket） |
| mqtt_bridge | Python + influxdb-client | — | MQTT → InfluxDB 持久化 |
| influxdb | influxdb:2.7 | 8086 | 时序数据库 |
| grafana | grafana/grafana:10.4 | 3000 | 可视化面板 |
| viz3d | nginx:alpine | 8080 | Three.js 3D 房间可视化 |

### 扩展层

| 组件 | 技术栈 | 端口 | 职责 |
|------|--------|------|------|
| FastAPI | Python + FastAPI | 8000 | Twin Service（状态机 + WebSocket + REST API） |
| Three.js Viewer | Three.js + CSS2DRenderer | 8000 | BIM 模型 3D 渲染 + 实时状态推送 |
| PostgreSQL | postgres:16-alpine | 5433 | 资产/传感器/告警规则关系存储 |

## 快速启动

### 1. 启动底座

```bash
cd room-digital-twin
cp .env.example .env
docker compose up -d
```

### 2. 启动扩展层

```bash
cd project
docker compose -f docker/docker-compose.yml up -d
```

## 数据流

```
传感器仿真 → MQTT (room/temperature, room/humidity, ...)
    ↓
mqtt_bridge → InfluxDB（时序存储）
    ↓
FastAPI (mqtt_consumer) → 状态机矩阵 → WebSocket → Three.js 前端
    ↓
PostgreSQL（资产资产映射 bim_guid ↔ asset_id）
```

## MQTT Topic 规范

| Topic | 方向 | Payload | 说明 |
|-------|------|---------|------|
| `room/temperature` | simulator → broker | `{"value": 23.5}` | 温度 °C |
| `room/humidity` | simulator → broker | `{"value": 58.4}` | 湿度 % |
| `room/fan_state` | simulator → broker | `{"value": "ON"}` | 风扇状态 |
| `room/fan_speed` | simulator → broker | `{"value": 1198}` | 风扇转速 RPM |
| `room/light` | simulator → broker | `{"value": 412.0}` | 光照 lux |
| `room/power` | simulator → broker | `{"value": 85.3}` | 功率 W |
| `room/fan/control` | host → broker → simulator | `ON` / `OFF` | 风扇远程控制 |

## 架构决策记录

详见 `Architecture.md`（ADR 格式）。

## AI 约束

详见 `AGENTS.md`（AI 行为锚定规范、高压红线、输出格式审计）。

## ROADMAP

详见 `ROADMAP.md`（Phase 1-4 演进路线图）。
