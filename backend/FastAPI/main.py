"""
Digital Twin Backend — Main Application
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
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("dt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Digital Twin Backend starting...")
    from database import get_pool
    try:
        pool = await get_pool()
        logger.info("PostgreSQL connection pool initialized")
    except Exception as e:
        logger.warning("PostgreSQL pool init failed: %s", e)

    from services.mqtt_consumer import start_mqtt
    mqtt_task = None
    try:
        mqtt_client = await start_mqtt()
        logger.info("MQTT consumer started")
    except Exception as e:
        logger.warning("MQTT not available (start without MQTT): %s", e)

    yield

    # Shutdown
    logger.info("Digital Twin Backend shutting down...")
    try:
        from services.mqtt_consumer import stop_mqtt
        await stop_mqtt()
    except Exception:
        pass
    await close_pool()


app = FastAPI(
    title="Digital Twin Data Center API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Three.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "digital-twin-backend"}

# Routers
app.include_router(assets.router)
app.include_router(sensors.router)
app.include_router(alarms.router)
app.include_router(rooms.router)
app.include_router(ws.router)

# Phase 3 — Three.js 前端静态文件（放最后，避免覆盖 api 路由）
app.mount("/", StaticFiles(directory="/app/viewer", html=True), name="viewer")
