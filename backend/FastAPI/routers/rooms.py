"""
Rooms API Router
"""
from fastapi import APIRouter

from database import get_pool

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


@router.get("")
async def list_rooms():
    pool = await get_pool()
    rows = await pool.fetch("SELECT * FROM room ORDER BY room_id")
    return [dict(r) for r in rows]


@router.get("/{room_id}")
async def get_room(room_id: int):
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM room WHERE room_id = $1", room_id)
    if not row:
        return {"error": "Room not found"}, 404
    return dict(row)


@router.get("/{room_id}/assets")
async def get_room_assets(room_id: int):
    pool = await get_pool()
    # Get room name first
    room = await pool.fetchrow("SELECT room_name FROM room WHERE room_id = $1", room_id)
    if not room:
        return {"error": "Room not found"}, 404
    rows = await pool.fetch(
        "SELECT * FROM asset WHERE room = $1 ORDER BY asset_id",
        room["room_name"]
    )
    return [dict(r) for r in rows]
