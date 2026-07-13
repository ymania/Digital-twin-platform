"""
Digital Twin Backend — Main Application

半成品框架：缺真实时序数据通路，但 REST API + WebSocket + Three.js 前端
开箱可用。接入真实 MQTT/Modbus 数据后全自动运行。
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import close_pool
from routers import assets, sensors, alarms, rooms, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("dt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=== Digital Twin Backend starting ===")

    # 1. PostgreSQL
    from database import get_pool
    try:
        pool = await get_pool()
        logger.info("PostgreSQL pool ready")
    except Exception as e:
        logger.warning("PostgreSQL unavailable: %s", e)

    # 2. MQTT consumer
    mqtt_task = None
    try:
        from services.mqtt_consumer import start_mqtt
        await start_mqtt()
        logger.info("MQTT consumer started")
    except Exception as e:
        logger.warning("MQTT consumer skipped: %s", e)

    # 3. Seed 默认状态（无 MQTT 时前端也能看到资产）
    await _seed_default_states()

    yield

    # Shutdown
    logger.info("=== Shutting down ===")
    try:
        from services.mqtt_consumer import stop_mqtt
        await stop_mqtt()
    except Exception:
        pass
    await close_pool()


async def _seed_default_states():
    """无 MQTT 数据时注入 PG seed 数据作为默认状态"""
    from core.state import GLOBAL_TWIN_MATRIX, TwinState
    try:
        from database import get_pool
        pool = await get_pool()
        rows = await pool.fetch("SELECT * FROM asset LIMIT 20")
        for row in rows:
            guid = row["bim_guid"] or f"BIM_{row['asset_id']}"
            GLOBAL_TWIN_MATRIX[guid] = TwinState(
                guid=guid,
                status="Normal",
                value=25.0,
                timestamp=0,
                metric="temperature",
            )
        logger.info("Seeded %d assets to state matrix", len(rows))
    except Exception as e:
        logger.warning("Seed skipped: %s", e)


app = FastAPI(
    title="Digital Twin Data Center API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "assets": len(ws.manager.active_connections)}


app.include_router(assets.router)
app.include_router(sensors.router)
app.include_router(alarms.router)
app.include_router(rooms.router)
app.include_router(ws.router)

# Three.js frontend (must be last — catches all)
app.mount("/", StaticFiles(directory="/app/viewer", html=True), name="viewer")
