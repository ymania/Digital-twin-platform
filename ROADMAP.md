# 🗺️ ROADMAP.md — 项目演进路线图

> 定义了平台从零到企业级落地的**四个核心演进阶段**。每个阶段都是一个**最小可行性闭环（MVP）**，必须在当前阶段完全通过验收定义（DoD）后，方可进入下一阶段。

---

## 📍 阶段总览：按层递进的敏捷闭环

```text
Phase 1: 物理感知与数据通路 (骨架) ──→ Phase 2: 资产建模与双轨存储 (记忆)
                                                    │
Phase 4: AI 预测与时空回放 (超感) ←── Phase 3: 孪生服务与实时渲染 (具象)
```

---

## 📌 Phase 1: 物理感知与数据通路闭环 (骨架构建)

**核心目标：** 攻克物理层到消息层的协议转换，建立具备"断网自愈"能力的边缘反射弧。

### 核心任务

1. ~~部署 Modbus Simulator，配置寄存器（`40001`~`40010`）高频吐出模拟温湿度数据。~~ ✅ 已实现
2. ~~搭建本地 Node-RED 容器，配置 `Modbus-Read` 节点实现 **1Hz** 频率的数据采集。~~
   **方案变更：Node-RED → Python 轻量采集器 `edge/python-collector/edge_collector.py`**
   原因：Node-RED 插件加载在 WSL 环境下反复卡住，换纯 Python 方案。
3. 在边缘端部署滑动窗口（Sliding Window）平滑节点（10秒均值）。 ✅ 内置在采集器中
4. 在边缘端配置轻量级 SQLite 缓存机制，实现断网存储（Store and Forward）。 ✅ 内置在采集器中
5. 部署云端 EMQX Broker，通过 MQTT 安全接入（QoS 2）接收边缘标准化报文。

### 📋 验收定义（DoD）

- [ ] 订阅 EMQX 主题 `telemetry/data`，能够持续收到标准化的 JSON 报文。
- [ ] 人为断开 EMQX 连接 1 分钟，边缘端无报错且将数据平滑写入 SQLite；恢复连接后，1 分钟内云端收到完整的补发（Backfill）报文。

### 涉及文件

| 文件 | 用途 |
|---|---|
| `docker/docker-compose.yml` | simulator, edge, emqx 容器编排 |
| `simulation/modbus/Dockerfile` | Modbus 模拟器容器 |
| `simulation/modbus/simulator.py` | 寄存器读写逻辑 |
| `edge/python-collector/edge_collector.py` | Python 边缘采集：Modbus→MQTT+滑动窗口+断网缓存 |
| `edge/python-collector/Dockerfile` | 边缘采集器容器 |

---

## 📌 Phase 2: 资产模型与时序存储双轨制 (记忆注入)

**核心目标：** 引入关系型与时序型"双轨数据库"，消除静态空间属性与动态时间流的耦合。

### 核心任务

1. 部署 PostgreSQL，创建 `asset`（资产表）与 `sensor`（测点映射表）实现一对多物理模型。
2. 升级 Node-RED 逻辑，在数据上报前去 PG 缓存中**动态注入资产 ID (asset_id)**，禁止将原始寄存器编号传向云端。
3. 部署 InfluxDB，在云端接收端编写摄入逻辑，将数据按 `Measurement(temperature)`、`Tag(asset_id, room)`、`Field(value)` 规范入库。
4. 配置 InfluxDB 的 Retention Policy（冷热分离），并编写全自动的 **1 小时时间窗口降采样任务（Downsampling Task）**。

### 📋 验收定义 (DoD)

- [ ] 在不重启 Node-RED 和云端系统的情况下，仅在 PostgreSQL 映射表中修改测点对应关系，时序数据库写入的数据能自动路由到新资产下（零硬编码验证）。
- [ ] InfluxDB 运行 24 小时后，在 `long_term` 存储策略中成功生成由 1 小时均值构成的降采样特征点。

### 涉及文件

| 文件 | 用途 |
|---|---|
| `docker/docker-compose.yml` | postgres, influxdb 容器编排 |
| `database/postgres/init.sql` | 资产/传感器/映射表 DDL + seed 数据 |
| `database/influx/setup.sh` | InfluxDB 任务与保留策略初始化 |
| `edge/NodeRED/flows.json` | 升级：PG 查询 → 动态注入 asset_id |
| `backend/FastAPI/services/mqtt_consumer.py` | MQTT → InfluxDB 写入 |

---

## 📌 Phase 3: 孪生服务与实时渲染大一统 (具象呈现)

**核心目标：** 建立统一的数字孪生服务层，用高并发、事件驱动的 WebSocket 管道彻底干掉传统的 HTTP 前端轮询。

### 核心任务

1. 基于 FastAPI 编写 `Twin Service`，常驻内存维护一套资产五大状态机矩阵（Five State Matrix）。
2. 在 Twin Service 内部引入事件总线，订阅 EMQX 的数据，实时驱动内存状态机跳转。
3. 建立 WebSocket 长连接通道，向前端提供扁平化的资产状态增量推送（`{"guid": "xxx", "status": "Warning"}`）。
4. 前端使用 Three.js/IFC.js 加载 WebBIM 模型，解析模型中构件的原生 GUID。
5. 前端订阅 WebSocket 管道，收到状态变更后，直接通过 GUID 索引到对应的 3D Mesh 进行着色切换。

### 📋 验收定义 (DoD)

- [ ] 打开 3D 浏览器，修改 Modbus 模拟器数值触发 Warning 阈值，3D 模型在 **50ms 内**全自动改变颜色（灰色→绿色→黄色→红色→蓝色）。
- [ ] 打开浏览器的 Network 面板，确认除了初始化加载外，**无任何 HTTP 轮询请求**，数据全量由 WebSocket 驱动。

### 涉及文件

| 文件 | 用途 |
|---|---|
| `backend/FastAPI/main.py` | FastAPI 启动 + 生命周期 |
| `backend/FastAPI/routers/ws.py` | WebSocket 连接管理 + 广播 |
| `backend/FastAPI/services/state_machine.py` | 资产状态机（5 状态矩阵） |
| `frontend/threejs/viewer/index.html` | 3D 浏览入口 |
| `frontend/threejs/viewer/app.js` | Three.js 场景 + WebSocket 更新 |
| `frontend/threejs/viewer/model.js` | IFC 模型加载 + GUID 解析 |
| `frontend/threejs/components/dashboard.html` | 仪表盘面板 |

### 资产五大状态矩阵

| 状态 | 颜色 | 含义 |
|---|---|---|
| Normal | 绿色 | 数据在正常范围 |
| Warning | 黄色 | 接近阈值（轻度预警） |
| Alarm | 红色 | 超过阈值（严重告警） |
| Maintenance | 橙色闪烁 | AI 预测到即将故障 |
| Offline | 灰色 | 设备心跳丢失 |

---

## 📌 Phase 4: 高级 AI 预测与时空回放 (超感闭环)

**核心目标：** 赋予数字孪生系统"穿越过去、预测未来"的生产级工程能力。

### 核心任务

1. 编写基于 Python 的独立 AI 异常检测 Agent，订阅时序数据流。
2. 利用孤立森林（Isolation Forest）或简易线性趋势预测算法，在温度即将超标前 **48 小时**计算出恶化概率。
3. 云端消息总线增加 `event/alarm` 异步主题，AI Agent 发现异常后向该主题发送预警信息。
4. Twin Service 接收 AI 预警，将设备状态推向 `Maintenance` 状态，3D 前端对应的模型开始高亮闪烁橙色。
5. 前端增加"时间滑块组件"，向 Twin Service 发送历史范围查询，系统调用 InfluxDB 降采样历史库，实现**整网历史时空回放**。

### 📋 验收定义 (DoD)

- [ ] 演示时，人为制造缓慢升温趋势，AI Agent 成功在达到临界点前发出告警，3D 大屏提前亮起橙色维护灯。
- [ ] 拖动时间轴到"昨天 15:30"，前端 3D 场景能够完全复原那个时间点全场设备的运行状态和红绿光斑。

### 涉及文件

| 文件 | 用途 |
|---|---|
| `ai/anomaly_detector.py` | Isolation Forest 异常检测 Agent |
| `ai/trend_predictor.py` | 线性趋势预测（48h 窗口） |
| `ai/agent_main.py` | AI Agent 主循环（MQTT 订阅/发布） |
| `ai/Dockerfile` | AI Agent 容器化 |
| `ai/requirements.txt` | 依赖：scikit-learn, pandas, gmqtt |
| `backend/FastAPI/services/state_machine.py` | 升级：Maintenance 状态闪烁逻辑 |
| `frontend/threejs/viewer/timeline.js` | 时间滑块 + 历史查询 |
| `frontend/threejs/components/timeline.html` | 时间轴 UI 组件 |
| `database/influx/setup.sh` | 降采样任务（供回放查询） |

---

## 📋 阶段依赖关系

```
Phase 1 (骨架)
  └── 为 Phase 2 提供原始数据流
Phase 2 (记忆)
  ├── 为 Phase 3 提供结构化数据查询
  └── 为 Phase 4 提供时序历史数据
Phase 3 (具象)
  └── 为 Phase 4 提供实时可视化底座
Phase 4 (超感)
  └── 闭环：AI 分析结果回到 Phase 3 的可视化层
```

---

## 📌 版本标记规范

每次 Phase 验收通过后，打 Git Tag：

```bash
git tag -a phase-1-complete -m "Phase 1: 物理感知与数据通路闭环 ✅"
git tag -a phase-2-complete -m "Phase 2: 资产模型与时序存储双轨制 ✅"
git tag -a phase-3-complete -m "Phase 3: 孪生服务与实时渲染大一统 ✅"
git tag -a phase-4-complete -m "Phase 4: AI预测与时空回放超感闭环 ✅"
```

---

## 📌 里程碑时间线（建议）

| Phase | 建议周期 | 交付 |
|---|---|---|
| Phase 1 | 1–2 天 | Docker 全栈容器化 + 数据通路 |
| Phase 2 | 1–2 天 | 数据库 + 动态资产映射 |
| Phase 3 | 2–3 天 | 3D 孪生页面 + 实时 WebSocket |
| Phase 4 | 2–3 天 | AI 预测 Agent + 时空回放 |

> 总工期约 7–10 天，适合作为 Showcase 项目的完整演示窗口。
