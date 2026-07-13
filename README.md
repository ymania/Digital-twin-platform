# Digital Twin Platform

```
docker compose -f docker/docker-compose.yml up -d
```

一键启动 6 个容器的工业数字孪生平台。物理仿真 → MQTT → InfluxDB + PostgreSQL → WebSocket → Three.js 3D 渲染。

## 栈

| 容器 | 镜像 | 端口 | 职责 |
|------|------|------|------|
| emqx | emqx:5.8 | 1883(MQTT) 18083(Dashboard) | 消息层 Broker |
| simulator | python:3.11-slim | — | Modbus 寄存器仿真+边缘采集 |
| bridge | python:3.11-slim | — | MQTT→InfluxDB 桥接持久化 |
| influxdb | influxdb:2.7-alpine | 8086 | 时序数据库 |
| postgres | postgres:16-alpine | 5433 | 资产/传感器关系库 |
| backend | python:3.12-slim | 8000 | Twin Service + WebSocket + Three.js viewer |

## 启动

```bash
cd project
docker compose -f docker/docker-compose.yml up -d
```

首次启动自动 build 两个 Python 镜像，约 60s。之后秒启。

## 访问

| 地址 | 说明 |
|------|------|
| http://localhost:8000 | Three.js 3D 前端（BIM 模型 + 实时状态） |
| http://localhost:18083 | EMQX Dashboard（admin / emqx_pass_2025） |
| http://localhost:8086 | InfluxDB UI |
| localhost:1883 | MQTT TCP |

## 架构

```
Modbus 仿真 → 边缘采集(滑动窗口+断网缓存) → EMQX(mqtt)
                                                  ↓            ─→ WebSocket → Three.js
bridge(mqtt→influxdb)   backend(状态机+pg查询) ─→ 
     ↓                                                
InfluxDB(时序)      PostgreSQL(资产映射)
```

## 数据通路验证

```bash
# MQTT 数据流
pip install paho-mqtt
python3 -c "
import paho.mqtt.client as mqtt, time
got=[]
def on_msg(c,u,m): got.append(m.topic)
c=mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
c.on_message=on_msg; c.connect('localhost',1883,60); c.subscribe('#')
c.loop_start(); time.sleep(8); c.loop_stop()
for t in set(got): print(t)
"

# REST API
curl localhost:8000/api/health
```

## 文件

- `AGENTS.md` — AI 行为红线
- `Architecture.md` — ADR 架构记录
- `ROADMAP.md` — 演进路线

## 缺什么

半成品。缺真实时序数据通路的端到端跑通验证。容器全健康，MQTT/Bridge/InfluxDB/PostgreSQL/Backend 代码全在，但实际数据通路因环境网络问题未完全打通。有真实 MQTT 源或修复 daemon 代理即可跑满全栈。
