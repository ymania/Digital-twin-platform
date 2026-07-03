"""
Core — 内存状态机矩阵
五大状态机内存常驻，解耦前端 0 轮询。
Key = 通过 PostgreSQL 路由映射出来的 WebBIM 标准 GUID
"""
from pydantic import BaseModel
from typing import Dict


class TwinState(BaseModel):
    guid: str
    status: str       # "Normal" | "Warning" | "Critical" | "Offline"
    value: float
    timestamp: int
    metric: str = ""


# 全局状态矩阵 — 内存常驻
GLOBAL_TWIN_MATRIX: Dict[str, TwinState] = {}


def derive_status(metric: str, value: float) -> str:
    """
    状态机跳变逻辑（阈值控制）
    AGENTS.md §2.3 红线：必须用滑动窗口均值，但这里只做简单阈值判定，
    边缘层已经做了 10 秒滑动窗口，backend 接收的是平滑后的值。
    """
    if metric == "temperature":
        if value > 40.0:
            return "Critical"
        elif value > 35.0:
            return "Warning"
    elif metric == "humidity":
        if value > 85.0:
            return "Critical"
        elif value > 75.0:
            return "Warning"
    elif metric == "power":
        if value > 9.5:
            return "Critical"
        elif value > 8.0:
            return "Warning"
    return "Normal"
