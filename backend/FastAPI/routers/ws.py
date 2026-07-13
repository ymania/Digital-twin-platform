"""
WebSocket Router — Twin State 实时推送

契约：
  1. 连接建立后立即推送全量 SNAPSHOT（当前全场物理快照）
  2. 状态/数值发生跳变时推送 INCREMENT（极致增量广播）
  3. 0 轮询，前端全靠 WebSocket 驱动
"""
import asyncio
import json
import logging
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("dt.ws")

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # 🌟 核心：一连接，立刻把内存里当前的"全场物理快照"一次性全量喂给前端
        from core.state import GLOBAL_TWIN_MATRIX
        snapshot = {
            k: v.model_dump() for k, v in GLOBAL_TWIN_MATRIX.items()
        }
        await websocket.send_json({
            "type": "SNAPSHOT",
            "data": snapshot,
        })
        logger.info("WebSocket connected (total=%d, snapshot_keys=%s)",
                     len(self.active_connections), list(snapshot.keys()))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket disconnected (remaining=%d)",
                     len(self.active_connections))

    async def broadcast(self, message: dict):
        """增量推送"""
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json({
                    "type": "INCREMENT",
                    "data": message,
                })
            except Exception as e:
                logger.warning("WebSocket broadcast error: %s", e)
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)


manager = ConnectionManager()


def broadcast_twin_state(state_dict: dict):
    """
    跨线程安全调用点 — mqtt_consumer 的 paho 回调线程通过此函数推送。
    实际生产中可使用 asyncio.run_coroutine_threadsafe。
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(manager.broadcast(state_dict))
    else:
        logger.warning("No running event loop, WebSocket broadcast skipped")


@router.websocket("/ws/twin")
async def ws_twin(websocket: WebSocket):
    """
    WebSocket 端点供 Three.js 前端连接。
    连接后立即推送 SNAPSHOT，后续持续接收 INCREMENT。
    客户端可发送 "ping" 保活。
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
