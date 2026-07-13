"""
Alarms API Router
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List

from database import get_pool

router = APIRouter(prefix="/api/alarms", tags=["Alarms"])


@router.get("/rules")
async def list_alarm_rules(sensor_id: int = None, enabled: bool = None):
    pool = await get_pool()
    conditions = []
    params = []
    idx = 1

    if sensor_id is not None:
        conditions.append(f"sensor_id = ${idx}")
        params.append(sensor_id)
        idx += 1
    if enabled is not None:
        conditions.append(f"enabled = ${idx}")
        params.append(enabled)
        idx += 1

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await pool.fetch(f"SELECT * FROM alarm_rule{where} ORDER BY rule_id", *params)
    return [dict(r) for r in rows]


@router.get("/events")
async def list_alarm_events(
    asset_id: int = None,
    severity: str = None,
    acknowledged: bool = None,
    limit: int = Query(default=50, le=500),
):
    pool = await get_pool()
    conditions = []
    params = []
    idx = 1

    if asset_id is not None:
        conditions.append(f"asset_id = ${idx}")
        params.append(asset_id)
        idx += 1
    if severity is not None:
        conditions.append(f"severity = ${idx}")
        params.append(severity)
        idx += 1
    if acknowledged is not None:
        conditions.append(f"acknowledged = ${idx}")
        params.append(acknowledged)
        idx += 1

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await pool.fetch(
        f"SELECT * FROM alarm_event{where} ORDER BY created_at DESC LIMIT ${idx}",
        *params, limit
    )
    return [dict(r) for r in rows]


@router.post("/events/{event_id}/acknowledge")
async def acknowledge_alarm(event_id: int):
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE alarm_event SET acknowledged = TRUE WHERE event_id = $1", event_id
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Alarm event not found")
    return {"status": "acknowledged", "event_id": event_id}
