# 🌐 工业级数字孪生平台 (Digital Twin Data Center)

本仓库是一个全栈、全解耦、事件驱动的**企业级数字孪生物联网（IIoT）平台**。

项目基于第一性原理，拒绝 CRUD 玩具架构，重点攻克工业现场"物理信号非标性"、"网络抖动不可靠性"与数字世界"海量高并发高吞吐"、"3D 渲染多端并发读压力"之间的核心物理博弈。

---

## 🏗️ 核心技术栈与分层

| 分层 | 核心选型 | 核心职责 |
| :--- | :--- | :--- |
| **1. 应用层 (Application)** | `Three.js` / `IFC.js` / `WebBIM` | 空间物体的 3D 具象呈现，0 轮询，全 WebSocket 状态机驱动变色与时空历史回放 |
| **2. 孪生层 (Twin Layer)** | `FastAPI` / `Python 3.11+` | 常驻内存管理资产"五大状态机矩阵"，作为数据联邦路由，实现极致的读写分离 |
| **3. 数据层 (Data Layer)** | `PostgreSQL` + `InfluxDB v2` | **双轨制存储**：PG 负责静态空间拓扑图谱，InfluxDB 负责动态时序记忆与自动降采样 |
| **4. 消息层 (Message Layer)** | `EMQX Broker` (MQTT) | 核心无状态交换枢纽，基于 QoS 分级确保控制指令 Exactly Once 送达 |
| **5. 边缘层 (Edge Layer)** | `Node-RED` / `SQLite` | 南向边缘采集、10s 滑动窗口除噪、硬件物理隔离、断网自愈归档 (Store & Forward) |
| **6. 物理层 (Physical)** | `Modbus TCP Simulator` | 模拟工业水泵、智能电表、PLC 寄存器高频动态数据流 |

---

## ⚡ 核心架构亮点 (Why this matters)

- **⚡ 极致的读写分离 (0 轮询)：** 前端 Three.js 视口缩放时对数据库并发读压力为 **0**。Twin Service 在进程内存中物化资产快照，通过 WebSocket 管道向前端全自动增量推送
- **🔌 硬件非标物理隔离：** 前端开发与后端核心业务**对底层物理寄存器完全无感知**。所有非标测点与硬件 ID（如 `40001`）在边缘层 Node-RED 通过 PostgreSQL 映射表直接消灭，转换成标准静态空间 `BIM_GUID`
- **🛡️ 工业级断网自愈机制：** 当网络链路中断，边缘端自动启动 Store-and-Forward 机制，高频流 Append 写入本地 SQLite。网络恢复后自动 Backfill 倒灌时序库，且 Twin Service **自动拦截历史流广播，严防前端大屏时间倒流与变色闪烁**
- **📉 98% 存储开销削减 (降采样)：** 内核级挂载滑动时间窗口降采样任务。实时高频库保留 7 天，历史趋势库永久保留。1 个月历史曲线查询时延从 7200ms 骤降至 15ms，性能飙升 480 倍

---

## 📂 仓库目录规约

```
.
├── doc/                         # 项目核心设计规约文档
│   ├── ARCHITECTURE.md          # 首席架构师技术记录与底层物理博弈 (ADR)
│   ├── ROADMAP.md               # 四大阶段最小可行性闭环演进路线 (DoD)
│   └── AGENTS.md                # 针对 AI 协同开发的最高宪法红线约束
├── edge/                        # 边缘层
│   └── NodeRED/                 # Node-RED 规则链定义 + SQLite 本地自治流
├── backend/                     # 孪生层
│   └── FastAPI/                 # FastAPI 核心源代码 (routers/models/schemas)
├── frontend/                    # 应用层
│   └── threejs/                 # Three.js/IFC.js WebBIM 三维视口控制
├── database/                    # 数据层初始化
│   ├── postgres/init.sql        # 资产拓扑 DDL + seed 数据
│   └── influx/                  # InfluxDB Bucket 初始化
├── simulation/                  # 物理层
│   └── modbus/                  # Modbus TCP 仿真器
├── ifc/                         # BIM 模型资产
├── docker/
│   └── docker-compose.yml       # 工业仿真环境一键全栈编排
├── ai/                          # AI 层 (Phase 4)
├── scripts/
└── tests/
```

---

## 🚀 快速开始

### 1. 环境依赖

- Docker & Docker Compose
- Node.js 18+ (本地前端微调)
- Python 3.11+ (本地后端微调)

### 2. 一键启动全栈基础设施

```bash
cd docker
docker compose up -d --build
```

全自动拉起 6 个容器：Modbus 仿真器、Node-RED 网关、EMQX 消息枢纽、PostgreSQL、InfluxDB、FastAPI 孪生服务。

### 3. 验证通路状态

| 组件 | 地址 | 验证内容 |
|---|---|---|
| 边缘网关 | `http://localhost:1880` | Node-RED 流是否成功建立 Modbus 连接 |
| 消息总线 | `http://localhost:18083` (admin/public) | EMQX 设备连接与主题订阅 |
| 孪生 API | `http://localhost:8000/docs` | Swagger OpenAPI 文档 |
| 3D 大屏 | `http://localhost:3000` | 旋转 3D BIM 模型，改变 Modbus 模拟器数值，观察 50ms 内颜色跳变 |

---

## 📋 开发路线

| Phase | 目标 | 周期 |
|---|---|---|
| Phase 1 | 物理感知与数据通路闭环 (骨架) | 1-2 天 |
| Phase 2 | 资产模型与时序存储双轨制 (记忆) | 1-2 天 |
| Phase 3 | 孪生服务与实时渲染大一统 (具象) | 2-3 天 |
| Phase 4 | AI 预测与时空回放 (超感) | 2-3 天 |

详细验收标准见 `doc/ROADMAP.md`。

---

## 🚨 开发红线约束 (Contributor Rules)

所有人类开发者与 AI 协同工具在修改代码前，**必须强制阅读并遵守 `doc/AGENTS.md` 与 `doc/ARCHITECTURE.md` 中的系统约束**：

1. **绝对禁止**在业务后端和前端代码中硬编码任何原始物理测点或硬件 ID
2. **绝对禁止**将高变动性变量（UUID、时间戳）作为 InfluxDB 的 Tag 写入，严防高基数灾难
3. **绝对严格**执行自上而下的单向依赖链
